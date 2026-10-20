"""Vérification avec Sentinel-1 (radar) : le trait de côte radar correspond-il à celui de Sentinel-2 ?

Le radar voit à travers les nuages, de jour comme de nuit : c'est la solution pour mesurer la côte juste
après une tempête. Ici, on prend une image radar proche de trois dates Sentinel-2, on trace le trait de côte
avec la même méthode (l'eau calme renvoie peu le signal radar : elle apparaît sombre), puis on compare les
positions sur les mêmes transects.

Usage : python verification_sentinel1.py
Sorties : donnees/traits_de_cote_S1_verification.geojson, resultats/verification_sentinel1.csv
"""

from datetime import date, timedelta

import geopandas as gpd
import numpy as np
import pandas as pd
import planetary_computer
import pystac_client
from pyproj import Transformer
from scipy.ndimage import median_filter
from skimage.filters import threshold_otsu

from config import CRS_METRIQUE, DONNEES, RESULTATS, ZONE_BBOX
from recul import positions_sur_transects
from traits_de_cote_sentinel2 import extraire_ligne, lire_bande
from transects import construire_transects, ligne_de_base

DATES_S2 = ["2019-02-22", "2023-01-22", "2025-01-06"]
FENETRE_JOURS = 6  # image radar à moins de 6 jours de l'image optique


def image_radar_proche(catalogue, jour: str):
    j = date.fromisoformat(jour)
    debut, fin = j - timedelta(days=FENETRE_JOURS), j + timedelta(days=FENETRE_JOURS)
    items = list(catalogue.search(collections=["sentinel-1-rtc"], bbox=list(ZONE_BBOX),
                                  datetime=f"{debut}/{fin}").items())
    return min(items, key=lambda i: abs(i.datetime.date() - j)) if items else None


def trait_radar(item):
    crs_image = item.properties.get("proj:code") or f"EPSG:{item.properties['proj:epsg']}"
    vers_image = Transformer.from_crs("EPSG:4326", crs_image, always_xy=True)
    ouest, sud, est, nord = ZONE_BBOX
    x0, y0 = vers_image.transform(ouest, sud)
    x1, y1 = vers_image.transform(est, nord)
    vv, transform, crs = lire_bande(item, "vv", (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
    valide = vv > 0
    db = 10 * np.log10(np.where(valide, vv, np.nan))
    db = median_filter(np.nan_to_num(db, nan=-30), size=5)  # atténue le « chatoiement » du radar
    indice = np.where(valide, -db, np.nan)                    # eau = signal faible = indice élevé
    seuil = float(threshold_otsu(indice[valide]))
    return extraire_ligne(indice, valide, seuil, transform), crs


def main():
    catalogue = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1",
                                          modifier=planetary_computer.sign_inplace)
    s2 = gpd.read_file(DONNEES / "traits_de_cote_S2_preliminaire.geojson")
    s2["date"] = pd.to_datetime(s2.date).dt.date.astype(str)

    radar = []
    for jour in DATES_S2:
        item = image_radar_proche(catalogue, jour)
        if item is None:
            print(f"{jour} : pas d'image radar à moins de {FENETRE_JOURS} jours")
            continue
        ligne, crs = trait_radar(item)
        print(f"{jour} : image radar du {item.datetime.date()} ({item.id}) -> "
              f"{'trait trouvé' if ligne is not None else 'trait non trouvé'}")
        if ligne is not None:
            radar.append(gpd.GeoDataFrame({"date": [jour], "date_radar": [str(item.datetime.date())]},
                                          geometry=[ligne], crs=crs).to_crs("EPSG:4326"))
    if not radar:
        raise SystemExit("Aucun trait de côte radar.")
    radar = gpd.GeoDataFrame(pd.concat(radar, ignore_index=True), crs="EPSG:4326")
    radar.to_file(DONNEES / "traits_de_cote_S1_verification.geojson", driver="GeoJSON")

    # Même transects que l'analyse principale, positions S1 et S2 aux mêmes dates
    s2m = s2.to_crs(CRS_METRIQUE)
    transects = construire_transects(ligne_de_base(s2m))
    p_s2 = positions_sur_transects(transects, s2m[s2m.date.isin(radar.date)])
    p_s1 = positions_sur_transects(transects, radar.to_crs(CRS_METRIQUE))
    comp = p_s2.merge(p_s1, on=["transect_id", "date"], suffixes=("_s2", "_s1"))
    comp["ecart_m"] = comp.distance_m_s1 - comp.distance_m_s2
    RESULTATS.mkdir(exist_ok=True)
    comp.to_csv(RESULTATS / "verification_sentinel1.csv", index=False, encoding="utf-8-sig")

    print("\nÉcart Sentinel-1 moins Sentinel-2 (m), par date :")
    resume = comp.groupby("date").ecart_m.agg(
        transects="count", ecart_median="median",
        ecart_absolu_median=lambda e: e.abs().median(),
        part_moins_de_20m=lambda e: (e.abs() < 20).mean() * 100).round(1)
    print(resume.to_string())


if __name__ == "__main__":
    main()
