"""Mesure de la position du trait de côte sur chaque transect, vitesses de recul et projections."""

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point

from config import ANNEES_PROJECTION, NIVEAUX_RISQUE, SEUILS_RECUL_M_AN


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


def statistiques(transects: gpd.GeoDataFrame, positions: pd.DataFrame, min_dates: int = 3) -> gpd.GeoDataFrame:
    """Calcule, pour chaque transect :
    - NSM : déplacement net entre le premier et le dernier trait de côte (m)
    - EPR : NSM divisé par la durée (m/an)
    - LRR : pente de la régression linéaire de la position dans le temps (m/an), et son R²
    Convention : valeur négative = la côte recule (érosion). recul_m_an = -LRR pour la lecture.
    """
    lignes = []
    for tid, groupe in positions.groupby("transect_id"):
        groupe = groupe.sort_values("date")
        if len(groupe) < min_dates:
            continue
        t = annee_decimale(groupe.date)
        x = groupe.distance_m.to_numpy()
        pente, ordonnee = np.polyfit(t, x, 1)
        predit = pente * t + ordonnee
        ss_res = float(((x - predit) ** 2).sum())
        ss_tot = float(((x - x.mean()) ** 2).sum())
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
        # Erreur type de la pente, pour une marge d'incertitude approximative (95 %)
        n = len(t)
        erreur_pente = np.sqrt(ss_res / (n - 2) / ((t - t.mean()) ** 2).sum()) if n > 2 else np.nan
        ligne = {"transect_id": tid, "nb_dates": n,
                 "premiere_date": str(pd.to_datetime(groupe.date.iloc[0]).date()),
                 "derniere_date": str(pd.to_datetime(groupe.date.iloc[-1]).date()),
                 "nsm_m": float(x[-1] - x[0]), "epr_m_an": float((x[-1] - x[0]) / (t[-1] - t[0])),
                 "lrr_m_an": float(pente), "r2": r2, "recul_m_an": float(-pente),
                 "position_actuelle_m": float(x[-1]), "annee_actuelle": float(t[-1])}
        for annee in ANNEES_PROJECTION:
            duree = annee - t[-1]
            ligne[f"position_{annee}_m"] = float(x[-1] + pente * duree)
            ligne[f"incertitude_{annee}_m"] = float(1.96 * erreur_pente * duree) if not np.isnan(erreur_pente) else np.nan
        ligne["risque"] = classer_risque(-pente)
        lignes.append(ligne)
    stats = pd.DataFrame(lignes)
    return transects.merge(stats, on="transect_id", how="inner")


def point_sur_transect(tr, distance_m: float) -> Point:
    return Point(tr.origine_x + tr.nx * distance_m, tr.origine_y + tr.ny * distance_m)


def traits_projetes(resultats: gpd.GeoDataFrame, annee: int) -> gpd.GeoDataFrame:
    """Relie les positions projetées de chaque transect pour dessiner le trait de côte futur."""
    res = resultats.sort_values("abscisse_m")
    points = [point_sur_transect(tr, getattr(tr, f"position_{annee}_m")) for tr in res.itertuples()]
    if len(points) < 2:
        return gpd.GeoDataFrame(geometry=[], crs=resultats.crs)
    return gpd.GeoDataFrame({"annee": [annee]}, geometry=[LineString(points)], crs=resultats.crs)
