"""Extraction des traits de côte à partir d'images Sentinel-2 L2A (Copernicus, lues via Microsoft Planetary Computer).

Pour chaque année, on prend l'image de saison sèche la moins nuageuse, on calcule l'indice
MNDWI (vert - SWIR) / (vert + SWIR), on sépare l'eau de la terre avec un seuil d'Otsu, puis on
cherche, ligne par ligne de l'image, la première terre rencontrée en venant de l'océan (à l'ouest).

C'est une première version pour tester la chaîne sur des données réelles et servir de secours.
Limites : pas de correction de la marée, l'écume des vagues peut décaler légèrement la ligne.

Usage : python traits_de_cote_sentinel2.py
Sortie : donnees/traits_de_cote_S2.geojson (+ apercus/ pour vérifier visuellement)
"""

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import planetary_computer
import pystac_client
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.windows import from_bounds
from scipy.ndimage import median_filter
from shapely.geometry import LineString, MultiLineString
from skimage.filters import threshold_otsu

from config import DONNEES, ZONE_BBOX

ANNEES = range(2016, 2026)
TERRE_CONSECUTIVE = 3      # pixels de terre d'affilée (30 m) pour ignorer l'écume et le bruit
SAUT_MAX_M = 150           # au-delà, on coupe la ligne (brèche, embouchure)
LISSAGE_LIGNES = 5         # filtre médian le long de la côte


def choisir_images():
    catalogue = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1",
                                          modifier=planetary_computer.sign_inplace)
    images = []
    for annee in ANNEES:
        recherche = catalogue.search(collections=["sentinel-2-l2a"], bbox=list(ZONE_BBOX),
                                     datetime=f"{annee - 1}-11-01/{annee}-05-31",
                                     query={"eo:cloud_cover": {"lt": 5}})
        candidates = sorted(recherche.items(), key=lambda i: i.properties["eo:cloud_cover"])
        if candidates:
            images.append(candidates[0])
    return images


def lire_bande(item, bande, bornes, forme=None):
    with rasterio.open(item.assets[bande].href) as src:
        fenetre = from_bounds(*bornes, transform=src.transform)
        donnees = src.read(1, window=fenetre, out_shape=forme, resampling=Resampling.bilinear,
                           boundless=True, fill_value=0).astype("float32")
        transform = src.window_transform(fenetre)
        if forme is not None:
            transform = transform * transform.scale(fenetre.width / forme[1], fenetre.height / forme[0])
        return donnees, transform, src.crs


def trait_de_cote(item):
    crs_image = item.properties["proj:code"] if "proj:code" in item.properties else f"EPSG:{item.properties['proj:epsg']}"
    vers_image = Transformer.from_crs("EPSG:4326", crs_image, always_xy=True)
    ouest, sud, est, nord = ZONE_BBOX
    x0, y0 = vers_image.transform(ouest, sud)
    x1, y1 = vers_image.transform(est, nord)
    bornes = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    vert, transform, crs = lire_bande(item, "B03", bornes)
    swir, _, _ = lire_bande(item, "B11", bornes, forme=vert.shape)
    valide = (vert > 0) & (swir > 0)
    # Depuis la version de traitement 04.00 (2022), les valeurs ont un décalage de +1000 à retirer
    if item.properties.get("s2:processing_baseline", "00.00") >= "04.00":
        vert = np.clip(vert - 1000, 1, None)
        swir = np.clip(swir - 1000, 1, None)
    mndwi = np.where(valide, (vert - swir) / np.maximum(vert + swir, 1e-6), np.nan)
    seuil = float(threshold_otsu(mndwi[valide]))
    return extraire_ligne(mndwi, valide, seuil, transform), seuil, mndwi, transform, crs


def extraire_ligne(indice, valide, seuil, transform):
    """Trait de côte à partir d'un indice où l'eau est au-dessus du seuil (MNDWI, ou radar inversé).

    Ligne par ligne de l'image : première terre (TERRE_CONSECUTIVE pixels d'affilée) en venant de l'ouest.
    Retourne une MultiLineString (coupée aux sauts), ou None.
    """
    eau = indice > seuil
    lignes_y, colonnes_x = [], []
    for r in range(eau.shape[0]):
        if not valide[r, :20].all() or not eau[r, :20].all():
            continue  # la ligne doit commencer dans l'océan
        terre = ~eau[r] & valide[r]
        suite = np.convolve(terre.astype(int), np.ones(TERRE_CONSECUTIVE, int), "valid") == TERRE_CONSECUTIVE
        if not suite.any():
            continue
        c = int(np.argmax(suite))
        # Position sous-pixel : interpolation du passage au seuil entre c-1 et c
        a, b = indice[r, c - 1], indice[r, c]
        frac = (a - seuil) / (a - b) if a != b else 0.5
        lignes_y.append(r)
        colonnes_x.append(c - 1 + float(np.clip(frac, 0, 1)) + 0.5)

    if len(colonnes_x) < 10:
        return None
    colonnes_x = median_filter(np.array(colonnes_x), size=LISSAGE_LIGNES)
    xs, ys = rasterio.transform.xy(transform, np.array(lignes_y) + 0.5, colonnes_x - 0.5, offset="ul")
    points = np.column_stack([xs, ys])

    # Coupure aux sauts (brèche, embouchure, lignes manquantes)
    segments, courant = [], [points[0]]
    for p, q in zip(points[:-1], points[1:]):
        if np.hypot(*(q - p)) > SAUT_MAX_M:
            segments.append(courant)
            courant = []
        courant.append(q)
    segments.append(courant)
    lignes = [LineString(s) for s in segments if len(s) >= 10]
    return MultiLineString(lignes) if lignes else None


def apercu(mndwi, transform, ligne, titre, chemin):
    gauche, haut = transform * (0, 0)
    droite, bas = transform * (mndwi.shape[1], mndwi.shape[0])
    fig, ax = plt.subplots(figsize=(5, 11))
    ax.imshow(mndwi, cmap="RdBu", vmin=-0.6, vmax=0.6, extent=(gauche, droite, bas, haut))
    for g in ligne.geoms:
        ax.plot(*g.xy, color="#ff7a00", linewidth=1)
    ax.set_title(titre, fontsize=9)
    ax.set_axis_off()
    fig.savefig(chemin, dpi=130, bbox_inches="tight")
    plt.close(fig)


def main():
    dossier_apercus = DONNEES / "apercus"
    dossier_apercus.mkdir(parents=True, exist_ok=True)
    resultats = []
    crs_commun = None
    for item in choisir_images():
        date = item.datetime.date().isoformat()
        print(f"{date}  {item.id}  nuages {item.properties['eo:cloud_cover']:.2f} %", flush=True)
        ligne, seuil, mndwi, transform, crs = trait_de_cote(item)
        if ligne is None:
            print("   trait de côte non trouvé, image ignorée")
            continue
        crs_commun = crs_commun or crs
        longueur = sum(g.length for g in ligne.geoms) / 1000
        print(f"   seuil Otsu {seuil:.3f}, {len(ligne.geoms)} segment(s), {longueur:.1f} km")
        apercu(mndwi, transform, ligne, f"{date} – MNDWI et trait de côte", dossier_apercus / f"trait_{date}.png")
        resultats.append({"date": date, "satname": "S2", "image": item.id, "seuil_otsu": round(seuil, 4), "geometry": ligne})
    gdf = gpd.GeoDataFrame(resultats, geometry="geometry", crs=crs_commun).to_crs("EPSG:4326")
    sortie = DONNEES / "traits_de_cote_S2.geojson"
    gdf.to_file(sortie, driver="GeoJSON")
    print(f"\n{len(gdf)} traits de côte écrits dans {sortie}")


if __name__ == "__main__":
    main()
