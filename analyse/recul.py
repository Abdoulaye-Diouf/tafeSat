"""Mesure de la position du trait de côte sur chaque transect, vitesses de recul et projections."""

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import theilslopes
from shapely.geometry import LineString, MultiLineString, Point

from config import (ANNEES_PROJECTION, ECART_DERNIERE_DATE_MAX_ANS, MIN_DATES_PROJECTION, MIN_DUREE_PROJECTION_ANS,
                    NIVEAUX_RISQUE, NON_EVALUE, SAUT_RUPTURE_M, SEUILS_RECUL_M_AN)


def annee_decimale(dates: pd.Series) -> np.ndarray:
    dates = pd.to_datetime(dates)
    return (dates.dt.year + (dates.dt.dayofyear - 1) / 365.25).to_numpy()


def positions_sur_transects(transects: gpd.GeoDataFrame, traits: gpd.GeoDataFrame) -> pd.DataFrame:
    """Distance (m) entre l'origine du transect et le trait de côte, positive vers la mer.

    Si un transect coupe plusieurs fois un trait de côte (rive du fleuve, bruit),
    on garde l'intersection la plus proche de la ligne de base.
    """
    mesures = []
    for _, tr in transects.iterrows():
        for _, trait in traits.iterrows():
            inter = tr.geometry.intersection(trait.geometry)
            if inter.is_empty:
                continue
            points = [inter] if isinstance(inter, Point) else [g for g in getattr(inter, "geoms", []) if isinstance(g, Point)]
            if not points:
                continue
            distances = [(p.x - tr.origine_x) * tr.nx + (p.y - tr.origine_y) * tr.ny for p in points]
            mesures.append({"transect_id": tr.transect_id, "date": trait.date,
                            "distance_m": min(distances, key=abs)})
    return pd.DataFrame(mesures)


def classer_risque(recul_m_an: float) -> str:
    if np.isnan(recul_m_an) or recul_m_an < SEUILS_RECUL_M_AN["moyen"]:
        return NIVEAUX_RISQUE[0]
    if recul_m_an < SEUILS_RECUL_M_AN["eleve"]:
        return NIVEAUX_RISQUE[1]
    if recul_m_an < SEUILS_RECUL_M_AN["tres_eleve"]:
        return NIVEAUX_RISQUE[2]
    return NIVEAUX_RISQUE[3]


def regression_lineaire(t: np.ndarray, x: np.ndarray) -> tuple[float, float]:
    """Pente (m/an) et R² de la régression linéaire classique (LRR, méthode DSAS)."""
    pente, ordonnee = np.polyfit(t, x, 1)
    ss_res = float(((x - (pente * t + ordonnee)) ** 2).sum())
    ss_tot = float(((x - x.mean()) ** 2).sum())
    return float(pente), (1 - ss_res / ss_tot if ss_tot > 0 else np.nan)


def statistiques(transects: gpd.GeoDataFrame, positions: pd.DataFrame, min_dates: int = 3) -> gpd.GeoDataFrame:
    """Calcule, pour chaque transect :
    - NSM : déplacement net entre le premier et le dernier trait de côte (m)
    - EPR : NSM divisé par la durée (m/an)
    - LRR : pente de la régression linéaire sur toute la série (m/an), et son R² (méthode DSAS)
    - rupture : saut de plus de SAUT_RUPTURE_M entre deux dates (zone de la brèche)
    - recul_m_an : vitesse robuste (Theil-Sen) après la dernière rupture, utilisée pour projeter
    Convention : distance positive vers la mer ; recul_m_an positif = la côte recule.
    """
    derniere_date_globale = annee_decimale(positions.date).max()
    lignes = []
    for tid, groupe in positions.groupby("transect_id"):
        groupe = groupe.sort_values("date")
        if len(groupe) < min_dates:
            continue
        t = annee_decimale(groupe.date)
        x = groupe.distance_m.to_numpy()
        lrr, r2 = regression_lineaire(t, x)

        # Dernière rupture : on ne garde que les dates qui suivent
        sauts = np.flatnonzero(np.abs(np.diff(x)) > SAUT_RUPTURE_M)
        debut = int(sauts[-1]) + 1 if len(sauts) else 0
        tp, xp = t[debut:], x[debut:]
        fiable = (len(tp) >= MIN_DATES_PROJECTION and tp[-1] - tp[0] >= MIN_DUREE_PROJECTION_ANS
                  and derniere_date_globale - tp[-1] <= ECART_DERNIERE_DATE_MAX_ANS)

        ligne = {"transect_id": tid, "nb_dates": len(t),
                 "premiere_date": str(pd.to_datetime(groupe.date.iloc[0]).date()),
                 "derniere_date": str(pd.to_datetime(groupe.date.iloc[-1]).date()),
                 "nsm_m": float(x[-1] - x[0]), "epr_m_an": float((x[-1] - x[0]) / (t[-1] - t[0])),
                 "lrr_m_an": lrr, "r2": r2,
                 "rupture": bool(len(sauts)),
                 "date_rupture": str(pd.to_datetime(groupe.date.iloc[debut]).date()) if len(sauts) else None,
                 "projection_fiable": bool(fiable),
                 "position_actuelle_m": float(x[-1]), "annee_actuelle": float(t[-1])}
        if fiable:
            pente, _, bas, haut = theilslopes(xp, tp, alpha=0.95)
            marge_pente = max(haut - pente, pente - bas)
            ligne["recul_m_an"] = float(-pente)
            for annee in ANNEES_PROJECTION:
                duree = annee - t[-1]
                ligne[f"position_{annee}_m"] = float(x[-1] + pente * duree)
                ligne[f"incertitude_{annee}_m"] = float(marge_pente * duree)
            ligne["risque"] = classer_risque(-pente)
        else:
            ligne["recul_m_an"] = np.nan
            for annee in ANNEES_PROJECTION:
                ligne[f"position_{annee}_m"] = np.nan
                ligne[f"incertitude_{annee}_m"] = np.nan
            ligne["risque"] = NON_EVALUE
        lignes.append(ligne)
    stats = pd.DataFrame(lignes)
    return transects.merge(stats, on="transect_id", how="inner")


def point_sur_transect(tr, distance_m: float) -> Point:
    return Point(tr.origine_x + tr.nx * distance_m, tr.origine_y + tr.ny * distance_m)


def traits_projetes(resultats: gpd.GeoDataFrame, annee: int) -> gpd.GeoDataFrame:
    """Relie les positions projetées de chaque transect pour dessiner le trait de côte futur.
    La ligne est coupée là où des tronçons ne sont pas projetés (non évalués ou absents)."""
    res = resultats.sort_values("abscisse_m")
    morceaux, courant, precedent = [], [], None
    for tr in res.itertuples():
        position = getattr(tr, f"position_{annee}_m")
        if np.isnan(position) or (precedent is not None and tr.transect_id != precedent + 1):
            if len(courant) >= 2:
                morceaux.append(LineString(courant))
            courant = []
        if not np.isnan(position):
            courant.append(point_sur_transect(tr, position))
        precedent = tr.transect_id
    if len(courant) >= 2:
        morceaux.append(LineString(courant))
    if not morceaux:
        return gpd.GeoDataFrame(geometry=[], crs=resultats.crs)
    return gpd.GeoDataFrame({"annee": [annee]}, geometry=[MultiLineString(morceaux)], crs=resultats.crs)
