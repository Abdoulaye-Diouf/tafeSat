"""Contrôle indépendant : nos traits de côte Sentinel-2 comparés à ceux extraits avec CoastSat (Abdoulaye DIOUF).

Deux méthodes différentes appliquées aux mêmes images : on mesure l'écart entre les deux traits de côte sur les mêmes
transects, aux dates communes. Un petit écart veut dire que le trait de côte ne dépend pas de la méthode choisie.

Usage : python comparaison_coastsat.py
Sortie : resultats/comparaison_coastsat.csv
"""

import geopandas as gpd
import pandas as pd

from config import CRS_METRIQUE, DONNEES, RESULTATS
from recul import positions_sur_transects
from transects import construire_transects, ligne_de_base


def lire(chemin):
    gdf = gpd.read_file(chemin).to_crs(CRS_METRIQUE)
    return gdf.assign(date=pd.to_datetime(gdf.date).dt.date.astype(str))


def main():
    nous = lire(DONNEES / "traits_de_cote_S2.geojson")
    coastsat = lire(DONNEES / "traits_de_cote_coastsat.geojson")
    transects = construire_transects(ligne_de_base(nous))
    communes = sorted(set(nous.date) & set(coastsat.date))
    p_nous = positions_sur_transects(transects, nous[nous.date.isin(communes)])
    p_cs = positions_sur_transects(transects, coastsat[coastsat.date.isin(communes)])
    comp = p_nous.merge(p_cs, on=["transect_id", "date"], suffixes=("_tefessat", "_coastsat"))
    comp["ecart_m"] = comp.distance_m_coastsat - comp.distance_m_tefessat
    resume = comp.groupby("date").ecart_m.agg(
        transects="count", ecart_median_m="median", ecart_absolu_median_m=lambda e: e.abs().median(),
        part_moins_de_20m_pct=lambda e: (e.abs() < 20).mean() * 100).round(1)
    RESULTATS.mkdir(exist_ok=True)
    resume.to_csv(RESULTATS / "comparaison_coastsat.csv", encoding="utf-8-sig")
    print(f"{len(communes)} dates communes")
    print(resume.to_string())


if __name__ == "__main__":
    main()
