"""Génère des traits de côte FICTIFS pour tester la chaîne avant d'avoir les vraies données.

Ces données ne sont pas des résultats : ne jamais les montrer au jury.
Usage : python analyse/donnees_test.py  ->  donnees/traits_de_cote_TEST.geojson
"""

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString

from config import CRS_WEB, DONNEES

rng = np.random.default_rng(42)
latitudes = np.linspace(15.80, 16.06, 300)
# Côte grossièrement nord-sud, un peu plus à l'ouest vers le sud
longitude_2016 = -16.505 - (16.06 - latitudes) * 0.12

lignes = []
for annee in range(2016, 2026):
    # Recul fictif : 0 à 3 m/an selon la latitude, plus du bruit de mesure de ~5 m
    recul_m = (annee - 2016) * (1.5 + 1.5 * np.sin(latitudes * 40))
    bruit_m = rng.normal(0, 5, size=latitudes.size)
    decalage_deg = (recul_m + bruit_m) / 107_000  # 1° de longitude ≈ 107 km à 16° N
    coords = list(zip(longitude_2016 + decalage_deg, latitudes))  # vers l'est = vers la terre
    lignes.append({"date": f"{annee}-02-15", "satname": "TEST", "geometry": LineString(coords)})

DONNEES.mkdir(exist_ok=True)
gpd.GeoDataFrame(lignes, geometry="geometry", crs=CRS_WEB).to_file(DONNEES / "traits_de_cote_TEST.geojson", driver="GeoJSON")
print("Traits de côte fictifs écrits dans donnees/traits_de_cote_TEST.geojson")
