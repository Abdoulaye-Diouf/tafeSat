"""Niveau de risque par tronçon : vitesse de recul, altitude et habitants exposés (méthode du dossier, §3)."""

import geopandas as gpd
import numpy as np
import rasterio
from pyproj import Transformer

from config import (ALTITUDE_BASSE_M, FICHIER_ALTITUDE, LARGEUR_ALTITUDE_M, NIVEAUX_RISQUE, NON_EVALUE,
                    SEUIL_HABITANTS_EXPOSES)


def altitude_cote(resultats: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Altitude de la crête (point le plus haut, m) sur les 200 premiers mètres côté terre.

    On prend le maximum et non la moyenne : là où la Langue de Barbarie est étroite, ces 200 m
    touchent le fleuve (altitude 0 dans le modèle), et c'est la crête de la dune qui arrête la mer.
    Limite : le Copernicus DEM est un modèle de surface, il inclut la hauteur des bâtiments."""
    if not FICHIER_ALTITUDE.exists():
        resultats["altitude_m"] = np.nan
        return resultats
    distances = np.arange(10, LARGEUR_ALTITUDE_M + 1, 10)
    with rasterio.open(FICHIER_ALTITUDE) as src:
        vers_dem = Transformer.from_crs(resultats.crs, src.crs, always_xy=True)
        cretes = []
        for tr in resultats.itertuples():
            d = tr.position_actuelle_m - distances  # vers la terre = distances plus petites
            x, y = vers_dem.transform(tr.origine_x + tr.nx * d, tr.origine_y + tr.ny * d)
            valeurs = np.array([v[0] for v in src.sample(zip(x, y))], dtype=float)
            if src.nodata is not None:
                valeurs[valeurs == src.nodata] = np.nan
            cretes.append(np.nanmax(valeurs) if np.isfinite(valeurs).any() else np.nan)
    resultats["altitude_m"] = np.round(cretes, 1)
    return resultats


def classer_risque_global(resultats: gpd.GeoDataFrame, annee: int) -> gpd.GeoDataFrame:
    """Part du niveau dû au recul, +1 si la côte est basse, +1 si beaucoup d'habitants sont exposés.
    Un tronçon qui ne recule pas reste au niveau faible : le risque mesuré ici est celui du recul."""
    resultats["risque_recul"] = resultats["risque"]
    evalue = resultats.risque.isin(NIVEAUX_RISQUE).to_numpy()
    niveau = resultats.risque.map({n: i for i, n in enumerate(NIVEAUX_RISQUE)}).fillna(-1).astype(int).to_numpy()
    basse = (resultats.altitude_m < ALTITUDE_BASSE_M).to_numpy()
    peuple = (resultats[f"habitants_menaces_{annee}"] >= SEUIL_HABITANTS_EXPOSES).to_numpy()
    en_recul = evalue & (niveau > 0)
    niveau = np.where(en_recul, np.minimum(niveau + basse + peuple, len(NIVEAUX_RISQUE) - 1), niveau)
    resultats["cote_basse"] = basse
    resultats["risque"] = np.where(evalue, [NIVEAUX_RISQUE[max(n, 0)] for n in niveau], NON_EVALUE)
    return resultats
