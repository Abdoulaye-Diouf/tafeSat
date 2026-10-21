"""Combine les traits de côte CoastSat d'Abdoulaye (nord, environ 37 dates par an) et les nôtres (toute la côte, une
date par an) en un seul fichier pour l'analyse.

Dans la bande de latitude couverte par CoastSat (Hydrobase – Goxu Mbacc), on garde ses traits de côte, beaucoup plus
nombreux : ils permettent de projeter la zone de la digue, où nous n'avons que 3 images depuis les travaux. Ailleurs
(brèche, Guéthie, nord de Goxu Mbacc), on garde nos traits de côte Sentinel-2.

Usage : python fusion_traits.py
Sortie : donnees/traits_de_cote_combines.geojson (colonne « source » : CoastSat ou Sentinel-2 TefesSat)
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from config import DONNEES

TRAITS_NOUS = DONNEES / "traits_de_cote_S2.geojson"
TRAITS_COASTSAT = DONNEES / "traits_de_cote_coastsat.geojson"  # CoastSat d'Abdoulaye, nord (Hydrobase – Goxu Mbacc)
TRAITS_COASTSAT_SUD = DONNEES / "traits_de_cote_coastsat_sud.geojson"  # CoastSat d'Abdoulaye, sud (brèche, Guéthie)
SORTIE = DONNEES / "traits_de_cote_combines.geojson"


def lire_coastsat():
    """Nord et sud CoastSat ; là où les deux se recouvrent, on garde le nord (série la plus longue)."""
    nord_cs = gpd.read_file(TRAITS_COASTSAT).to_crs("EPSG:4326")
    if not TRAITS_COASTSAT_SUD.exists():
        return nord_cs
    sud_cs = gpd.read_file(TRAITS_COASTSAT_SUD).to_crs("EPSG:4326")
    limite = nord_cs.total_bounds[1]
    sud_cs["geometry"] = sud_cs.geometry.intersection(box(-180, -90, 180, limite))
    sud_cs = sud_cs[~sud_cs.geometry.is_empty]
    return gpd.GeoDataFrame(pd.concat([nord_cs, sud_cs], ignore_index=True), crs="EPSG:4326")


def main():
    nous = gpd.read_file(TRAITS_NOUS).to_crs("EPSG:4326")
    coastsat = lire_coastsat()
    ouest, sud, est, nord = coastsat.total_bounds
    bande = box(-180, sud, 180, nord)  # bande de latitude couverte par CoastSat

    nous["geometry"] = nous.geometry.difference(bande)
    nous = nous[~nous.geometry.is_empty]
    nous = nous.assign(date=pd.to_datetime(nous.date).dt.date.astype(str), source="Sentinel-2 TefesSat")
    coastsat = coastsat.assign(date=pd.to_datetime(coastsat.date).dt.date.astype(str), source="CoastSat (Abdoulaye DIOUF)")

    combines = gpd.GeoDataFrame(pd.concat([nous[["date", "source", "geometry"]], coastsat[["date", "source", "geometry"]]],
                                          ignore_index=True), crs="EPSG:4326")
    combines.to_file(SORTIE, driver="GeoJSON")
    print(f"CoastSat : {len(coastsat)} traits de côte, latitudes {sud:.3f} à {nord:.3f}")
    print(f"Sentinel-2 TefesSat : {len(nous)} traits de côte hors de cette bande")
    print(f"-> {SORTIE.name} : {len(combines)} traits de côte")


if __name__ == "__main__":
    main()
