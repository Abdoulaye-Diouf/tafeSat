"""Bande menacée par la mer et bâtiments, équipements et habitants exposés."""

import geopandas as gpd
import numpy as np
from shapely.geometry import Polygon

from config import ESPACEMENT_TRANSECTS_M, PERSONNES_PAR_BATIMENT


def bandes_menacees(resultats: gpd.GeoDataFrame, annee: int) -> gpd.GeoDataFrame:
    """Pour chaque transect en recul : rectangle entre la côte actuelle et la côte projetée,
    large d'un espacement de transect (une « tranche » de côte de 50 m)."""
    demi = ESPACEMENT_TRANSECTS_M / 2
    lignes = []
    for tr in resultats.itertuples():
        actuelle, future = tr.position_actuelle_m, getattr(tr, f"position_{annee}_m")
        if future >= actuelle:  # la côte avance ou reste stable : rien de menacé
            continue
        # Vecteur le long de la côte (perpendiculaire au transect)
        lx, ly = -tr.ny, tr.nx
        coins = []
        for d, s in [(actuelle, -1), (actuelle, 1), (future, 1), (future, -1)]:
            cx, cy = tr.origine_x + tr.nx * d, tr.origine_y + tr.ny * d
            coins.append((cx + s * lx * demi, cy + s * ly * demi))
        lignes.append({"transect_id": tr.transect_id, "annee": annee, "geometry": Polygon(coins)})
    return gpd.GeoDataFrame(lignes, geometry="geometry", crs=resultats.crs)


def compter_exposition(resultats: gpd.GeoDataFrame, bandes: gpd.GeoDataFrame,
                       batiments: gpd.GeoDataFrame | None, equipements: gpd.GeoDataFrame | None,
                       annee: int) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Ajoute aux résultats le nombre de bâtiments et d'équipements dans la bande menacée."""
    col_bat, col_eq = f"batiments_menaces_{annee}", f"equipements_menaces_{annee}"
    resultats[col_bat] = 0
    resultats[col_eq] = 0
    batiments_menaces = gpd.GeoDataFrame(geometry=[], crs=resultats.crs)
    if len(bandes) and batiments is not None and len(batiments):
        jointure = gpd.sjoin(batiments.to_crs(resultats.crs), bandes[["transect_id", "geometry"]],
                             predicate="intersects", how="inner")
        jointure = jointure[~jointure.index.duplicated()]  # un bâtiment compté une seule fois
        comptes = jointure.groupby("transect_id").size()
        resultats[col_bat] = resultats.transect_id.map(comptes).fillna(0).astype(int)
        batiments_menaces = jointure.drop(columns="index_right")
    if len(bandes) and equipements is not None and len(equipements):
        jointure = gpd.sjoin(equipements.to_crs(resultats.crs), bandes[["transect_id", "geometry"]],
                             predicate="within", how="inner")
        comptes = jointure.groupby("transect_id").size()
        resultats[col_eq] = resultats.transect_id.map(comptes).fillna(0).astype(int)
    if PERSONNES_PAR_BATIMENT:
        resultats[f"habitants_estimes_{annee}"] = resultats[col_bat] * PERSONNES_PAR_BATIMENT
    return resultats, batiments_menaces


def rattacher_quartiers(resultats: gpd.GeoDataFrame, quartiers: gpd.GeoDataFrame | None) -> gpd.GeoDataFrame:
    """Associe chaque transect au nom de quartier OSM le plus proche."""
    if quartiers is None or not len(quartiers):
        resultats["quartier"] = None
        return resultats
    q = quartiers.to_crs(resultats.crs)
    origines = gpd.GeoSeries(gpd.points_from_xy(resultats.origine_x, resultats.origine_y), crs=resultats.crs)
    distances = np.array([[o.distance(p) for p in q.geometry] for o in origines])
    resultats["quartier"] = q.nom.to_numpy()[distances.argmin(axis=1)]
    return resultats
