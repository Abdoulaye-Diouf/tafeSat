"""Télécharge l'altitude (Copernicus DEM, 30 m) et la population (WorldPop 2025, 100 m) de la zone d'étude.

Usage : python telecharger_altitude_population.py
Sorties : donnees/altitude_copernicus_dem.tif, donnees/population_worldpop_2025.tif
"""

import planetary_computer
import pystac_client
import rasterio
import requests
from rasterio.merge import merge
from rasterio.windows import from_bounds

from config import DONNEES, ZONE_BBOX

WORLDPOP_URL = ("https://data.worldpop.org/GIS/Population/Global_2015_2030/R2024B/2025/SEN/v1/100m/"
                "constrained/sen_pop_2025_CN_100m_R2024B_v1.tif")
MARGE_DEG = 0.01  # petite marge autour de la zone


def bornes_avec_marge():
    ouest, sud, est, nord = ZONE_BBOX
    return ouest - MARGE_DEG, sud - MARGE_DEG, est + MARGE_DEG, nord + MARGE_DEG


def altitude():
    catalogue = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1",
                                          modifier=planetary_computer.sign_inplace)
    tuiles = list(catalogue.search(collections=["cop-dem-glo-30"], bbox=list(ZONE_BBOX)).items())
    print(f"Copernicus DEM : {len(tuiles)} tuile(s)")
    sources = [rasterio.open(t.assets["data"].href) for t in tuiles]
    mosaique, transform = merge(sources, bounds=bornes_avec_marge())
    profil = sources[0].profile | {"height": mosaique.shape[1], "width": mosaique.shape[2],
                                   "transform": transform, "driver": "GTiff", "compress": "deflate"}
    for s in sources:
        s.close()
    sortie = DONNEES / "altitude_copernicus_dem.tif"
    with rasterio.open(sortie, "w", **profil) as dst:
        dst.write(mosaique)
    print(f"   {sortie.name} : {mosaique.shape[2]} x {mosaique.shape[1]} pixels, "
          f"altitude de {mosaique.min():.1f} à {mosaique.max():.1f} m")


def population():
    # Le serveur WorldPop ne permet pas de lire une partie du fichier : on télécharge le pays entier (18 Mo)
    pays = DONNEES / "cache_worldpop" / WORLDPOP_URL.rsplit("/", 1)[1]
    if not pays.exists():
        pays.parent.mkdir(parents=True, exist_ok=True)
        reponse = requests.get(WORLDPOP_URL, timeout=300)
        reponse.raise_for_status()
        pays.write_bytes(reponse.content)
    with rasterio.open(pays) as src:
        fenetre = from_bounds(*bornes_avec_marge(), transform=src.transform).round_offsets().round_lengths()
        donnees = src.read(1, window=fenetre)
        profil = src.profile | {"height": donnees.shape[0], "width": donnees.shape[1],
                                "transform": src.window_transform(fenetre), "driver": "GTiff",
                                "compress": "deflate"}
        nodata = src.nodata
    sortie = DONNEES / "population_worldpop_2025.tif"
    with rasterio.open(sortie, "w", **profil) as dst:
        dst.write(donnees, 1)
    total = donnees[donnees != nodata].sum() if nodata is not None else donnees.sum()
    habitants = f"{total:,.0f}".replace(",", " ")
    print(f"WorldPop 2025 : {sortie.name}, environ {habitants} habitants dans la zone")


if __name__ == "__main__":
    if not (DONNEES / "altitude_copernicus_dem.tif").exists():
        altitude()
    population()
