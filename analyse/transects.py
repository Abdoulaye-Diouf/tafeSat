"""Construction de la ligne de base et des transects perpendiculaires à la côte."""

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import linemerge

from config import (CRS_METRIQUE, DEMI_LONGUEUR_TRANSECT_M, ESPACEMENT_TRANSECTS_M, POINT_EN_MER,
                    SIMPLIFICATION_LIGNE_DE_BASE_M, ZONE_INFLUENCE_DIGUE_LAT)


def transects_zone_digue(transects: gpd.GeoDataFrame) -> set:
    """Numéros des transects de la zone influencée par la digue de Guet Ndar (d'après la latitude de leur origine)."""
    latitudes = gpd.GeoSeries(gpd.points_from_xy(transects.origine_x, transects.origine_y),
                              crs=transects.crs).to_crs("EPSG:4326").y.to_numpy()
    sud, nord = ZONE_INFLUENCE_DIGUE_LAT
    return set(transects.transect_id.to_numpy()[(latitudes >= sud) & (latitudes <= nord)])


def ligne_principale(geometrie) -> LineString:
    """Garde la plus longue ligne d'une géométrie (le trait de côte océanique)."""
    if isinstance(geometrie, MultiLineString):
        fusion = linemerge(geometrie)
        geometrie = fusion if isinstance(fusion, LineString) else max(fusion.geoms, key=lambda g: g.length)
    return geometrie


def relier_nord_sud(geometrie) -> LineString:
    """Relie les morceaux d'un trait de côte (coupé aux embouchures) en une seule ligne, du nord au sud."""
    if isinstance(geometrie, LineString):
        return geometrie
    morceaux = sorted(geometrie.geoms, key=lambda g: -max(y for _, y in g.coords))
    coords = []
    for g in morceaux:
        c = list(g.coords)
        if c[0][1] < c[-1][1]:  # orienter chaque morceau du nord vers le sud
            c.reverse()
        coords.extend(c)
    return LineString(coords)


def ligne_de_base(traits: gpd.GeoDataFrame) -> LineString:
    """Ligne de base = le trait de côte le plus ancien, morceaux reliés du nord au sud, puis lissé."""
    plus_ancien = traits.sort_values("date").iloc[0].geometry
    return relier_nord_sud(plus_ancien).simplify(SIMPLIFICATION_LIGNE_DE_BASE_M)


def construire_transects(base: LineString) -> gpd.GeoDataFrame:
    """Transects perpendiculaires à la ligne de base, orientés de la terre vers la mer."""
    mer = gpd.GeoSeries([Point(POINT_EN_MER)], crs="EPSG:4326").to_crs(CRS_METRIQUE).iloc[0]
    lignes = []
    for i, d in enumerate(np.arange(0, base.length, ESPACEMENT_TRANSECTS_M)):
        origine = base.interpolate(d)
        avant = base.interpolate(max(d - 5, 0))
        apres = base.interpolate(min(d + 5, base.length))
        tx, ty = apres.x - avant.x, apres.y - avant.y
        norme = np.hypot(tx, ty)
        if norme == 0:
            continue
        nx, ny = -ty / norme, tx / norme  # normale à la côte
        # On oriente la normale vers la mer
        if (mer.x - origine.x) * nx + (mer.y - origine.y) * ny < 0:
            nx, ny = -nx, -ny
        L = DEMI_LONGUEUR_TRANSECT_M
        terre = (origine.x - nx * L, origine.y - ny * L)
        large = (origine.x + nx * L, origine.y + ny * L)
        lignes.append({"transect_id": i, "abscisse_m": float(d), "nx": nx, "ny": ny,
                       "origine_x": origine.x, "origine_y": origine.y, "geometry": LineString([terre, large])})
    return gpd.GeoDataFrame(lignes, geometry="geometry", crs=CRS_METRIQUE)
