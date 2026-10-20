"""Bande menacée par la mer et bâtiments, équipements et habitants exposés."""

import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import Polygon

from config import (CONFIANCE_MIN_GOOGLE, CRS_METRIQUE, ECART_DERNIERE_DATE_MAX_ANS, ESPACEMENT_TRANSECTS_M, FICHIER_POPULATION,
                    PERSONNES_PAR_BATIMENT, QUARTIER_DISTANCE_COTE_MAX_M, QUARTIER_DISTANCE_TRANSECT_MAX_M)


def fusionner_batiments(osm: gpd.GeoDataFrame | None, google: gpd.GeoDataFrame | None) -> gpd.GeoDataFrame | None:
    """Tous les bâtiments OSM, plus les bâtiments Google/Microsoft qui ne recouvrent aucun bâtiment OSM."""
    if google is None:
        return osm
    google = google[(google.confiance.isna()) | (google.confiance >= CONFIANCE_MIN_GOOGLE)]
    if osm is None:
        return google.assign(source=google.source)
    osm = osm.to_crs(google.crs)
    deja_dans_osm = gpd.sjoin(google, osm[["geometry"]], predicate="intersects", how="inner").index.unique()
    ajouts = google.drop(index=deja_dans_osm)
    fusion = gpd.pd.concat([osm[["geometry"]].assign(source="osm"), ajouts[["source", "geometry"]]],
                           ignore_index=True)
    return gpd.GeoDataFrame(fusion, geometry="geometry", crs=google.crs)


def habitants_par_batiment(batiments: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Répartit la population WorldPop (carrés de 100 m) entre les bâtiments de chaque carré,
    au prorata de leur surface. Ajoute la colonne « habitants »."""
    batiments = batiments.copy()
    if not FICHIER_POPULATION.exists():
        batiments["habitants"] = PERSONNES_PAR_BATIMENT or np.nan
        return batiments
    with rasterio.open(FICHIER_POPULATION) as src:
        pop = src.read(1)
        nodata = src.nodata
        metrique = batiments.geometry.to_crs(CRS_METRIQUE)
        centres = metrique.centroid.to_crs(src.crs)
        lignes, colonnes = rasterio.transform.rowcol(src.transform, centres.x, centres.y)
    lignes, colonnes = np.asarray(lignes), np.asarray(colonnes)
    dedans = (lignes >= 0) & (lignes < pop.shape[0]) & (colonnes >= 0) & (colonnes < pop.shape[1])
    valeur = np.zeros(len(batiments))
    valeur[dedans] = pop[lignes[dedans], colonnes[dedans]]
    if nodata is not None:
        valeur[valeur == nodata] = 0
    surface = metrique.area.to_numpy()
    carre = np.where(dedans, lignes * pop.shape[1] + colonnes, -1)
    surface_du_carre = gpd.pd.Series(surface).groupby(carre).transform("sum").to_numpy()
    batiments["habitants"] = np.where(surface_du_carre > 0, valeur * surface / surface_du_carre, 0)
    return batiments


def bandes_menacees(resultats: gpd.GeoDataFrame, annee: int) -> gpd.GeoDataFrame:
    """Pour chaque transect en recul : rectangle entre la côte actuelle et la côte projetée,
    large d'un espacement de transect (une « tranche » de côte de 50 m)."""
    demi = ESPACEMENT_TRANSECTS_M / 2
    lignes = []
    for tr in resultats.itertuples():
        actuelle, future = tr.position_actuelle_m, getattr(tr, f"position_{annee}_m")
        if np.isnan(future) or future >= actuelle:  # non projeté, ou la côte avance : rien de menacé
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
    """Ajoute aux résultats le nombre de bâtiments, d'habitants et d'équipements dans la bande menacée."""
    col_bat, col_eq, col_hab = f"batiments_menaces_{annee}", f"equipements_menaces_{annee}", f"habitants_menaces_{annee}"
    resultats[col_bat] = 0
    resultats[col_eq] = 0
    resultats[col_hab] = 0.0
    batiments_menaces = gpd.GeoDataFrame(geometry=[], crs=resultats.crs)
    if len(bandes) and batiments is not None and len(batiments):
        jointure = gpd.sjoin(batiments.to_crs(resultats.crs), bandes[["transect_id", "geometry"]],
                             predicate="intersects", how="inner")
        jointure = jointure[~jointure.index.duplicated()]  # un bâtiment compté une seule fois
        comptes = jointure.groupby("transect_id").size()
        resultats[col_bat] = resultats.transect_id.map(comptes).fillna(0).astype(int)
        if "habitants" in jointure.columns:
            habitants = jointure.groupby("transect_id").habitants.sum()
            resultats[col_hab] = resultats.transect_id.map(habitants).fillna(0).round(1)
        batiments_menaces = jointure.drop(columns="index_right")
    if len(bandes) and equipements is not None and len(equipements):
        jointure = gpd.sjoin(equipements.to_crs(resultats.crs), bandes[["transect_id", "geometry"]],
                             predicate="within", how="inner")
        comptes = jointure.groupby("transect_id").size()
        resultats[col_eq] = resultats.transect_id.map(comptes).fillna(0).astype(int)
    return resultats, batiments_menaces


def _distance_maison_la_plus_proche(resultats, batiments, colonne_position):
    """Distance (m) entre la position de la côte donnée par `colonne_position` et le bâtiment le plus proche."""
    sel = resultats[resultats[colonne_position].notna()]
    if batiments is None or not len(batiments) or not len(sel):
        return gpd.pd.Series(dtype=float)
    points = gpd.GeoDataFrame(
        {"transect_id": sel.transect_id.to_numpy()},
        geometry=gpd.points_from_xy(sel.origine_x + sel.nx * sel[colonne_position],
                                    sel.origine_y + sel.ny * sel[colonne_position]),
        crs=resultats.crs)
    proches = gpd.sjoin_nearest(points, batiments[["geometry"]].to_crs(resultats.crs), distance_col="d")
    return proches.groupby("transect_id").d.min().round(0)


def marge_avant_batiments(resultats: gpd.GeoDataFrame, batiments: gpd.GeoDataFrame | None,
                          annee: int | None) -> gpd.GeoDataFrame:
    """Distance (m) entre la côte et le bâtiment le plus proche.

    annee=None : côte actuelle (dernière image), sans projection -> marge_batiments_actuelle_m.
    annee=2030… : côte projetée -> marge_batiments_{annee}_m, et le pire cas (marge moins la marge
    d'erreur de la projection) -> pire_cas_marge_{annee}_m ; une valeur négative veut dire que des
    maisons pourraient être atteintes si le recul est au haut de la fourchette.
    """
    if annee is None:
        # Seulement pour les tronçons mesurés sur une image récente : sinon la « position actuelle » est ancienne
        recents = resultats[resultats.annee_actuelle.max() - resultats.annee_actuelle <= ECART_DERNIERE_DATE_MAX_ANS]
        marges = _distance_maison_la_plus_proche(recents, batiments, "position_actuelle_m")
        resultats["marge_batiments_actuelle_m"] = resultats.transect_id.map(marges)
        return resultats
    colonne = f"marge_batiments_{annee}_m"
    marges = _distance_maison_la_plus_proche(resultats, batiments, f"position_{annee}_m")
    resultats[colonne] = resultats.transect_id.map(marges)
    resultats[f"pire_cas_marge_{annee}_m"] = (resultats[colonne] - resultats[f"incertitude_{annee}_m"]).round(0)
    return resultats


def rattacher_quartiers(resultats: gpd.GeoDataFrame, quartiers: gpd.GeoDataFrame | None,
                        base) -> gpd.GeoDataFrame:
    """Associe chaque transect au quartier OSM côtier le plus proche (lieux à moins de 1 km de la côte)."""
    if quartiers is None or not len(quartiers):
        resultats["quartier"] = None
        return resultats
    q = quartiers.to_crs(resultats.crs)
    q = q[q.distance(base) <= QUARTIER_DISTANCE_COTE_MAX_M]
    origines = gpd.GeoSeries(gpd.points_from_xy(resultats.origine_x, resultats.origine_y), crs=resultats.crs)
    distances = np.array([[o.distance(p) for p in q.geometry] for o in origines])
    plus_proche = distances.argmin(axis=1)
    noms = q.nom.to_numpy()[plus_proche]
    resultats["quartier"] = np.where(distances.min(axis=1) <= QUARTIER_DISTANCE_TRANSECT_MAX_M, noms,
                                     "Côte non habitée")
    return resultats
