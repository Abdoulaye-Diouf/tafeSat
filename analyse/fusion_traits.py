"""Combine les traits de côte CoastSat d'Abdoulaye et les nôtres (toute la côte, une date par an) en un seul fichier.

- Au nord (Hydrobase – Goxu Mbacc, environ 37 dates par an), les traits CoastSat REMPLACENT les nôtres : ils
  permettent de projeter la zone de la digue, où nous n'avons que 3 images depuis les travaux.
- Au sud (brèche, Guéthie, Tassinère), les traits CoastSat ne croisent qu'une partie des tronçons : ils s'AJOUTENT
  aux nôtres, sans rien retirer. Les deux sources concordent à quelques mètres près aux dates communes
  (voir comparaison_coastsat.py), ce qui justifie de les mélanger.
- Ailleurs, nos traits de côte Sentinel-2.

Usage : python fusion_traits.py
Sortie : donnees/traits_de_cote_combines.geojson (colonne « source »)
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from config import DONNEES

TRAITS_NOUS = DONNEES / "traits_de_cote_S2.geojson"
TRAITS_COASTSAT = DONNEES / "traits_de_cote_coastsat.geojson"  # CoastSat d'Abdoulaye, nord (Hydrobase – Goxu Mbacc)
TRAITS_COASTSAT_SUD = DONNEES / "traits_de_cote_coastsat_sud.geojson"  # CoastSat d'Abdoulaye, sud (brèche, Guéthie)
SORTIE = DONNEES / "traits_de_cote_combines.geojson"


def lire(chemin, source):
    gdf = gpd.read_file(chemin).to_crs("EPSG:4326")
    return gdf.assign(date=pd.to_datetime(gdf.date).dt.date.astype(str), source=source)


def main():
    nous = lire(TRAITS_NOUS, "Sentinel-2 TefesSat")
    nord_cs = lire(TRAITS_COASTSAT, "CoastSat nord (Abdoulaye DIOUF)")
    _, sud, _, nord = nord_cs.total_bounds
    bande_nord = box(-180, sud, 180, nord)  # bande de latitude couverte par le nord CoastSat

    nous["geometry"] = nous.geometry.difference(bande_nord)
    nous = nous[~nous.geometry.is_empty]
    morceaux = [nous, nord_cs]
    if TRAITS_COASTSAT_SUD.exists():
        sud_cs = lire(TRAITS_COASTSAT_SUD, "CoastSat sud (Abdoulaye DIOUF)")
        sud_cs["geometry"] = sud_cs.geometry.intersection(box(-180, -90, 180, sud))  # sous la bande du nord
        sud_cs = sud_cs[~sud_cs.geometry.is_empty]
        morceaux.append(sud_cs)

    combines = gpd.GeoDataFrame(pd.concat([m[["date", "source", "geometry"]] for m in morceaux], ignore_index=True),
                                crs="EPSG:4326")
    combines.to_file(SORTIE, driver="GeoJSON")
    print(f"Traits de côte par source : {combines.source.value_counts().to_dict()}")
    print(f"-> {SORTIE.name} : {len(combines)} traits de côte")


if __name__ == "__main__":
    main()
