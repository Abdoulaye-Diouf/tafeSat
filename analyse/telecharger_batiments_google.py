"""Télécharge les bâtiments Google Open Buildings (et Microsoft) de la zone d'étude.

Source : jeu fusionné Google + Microsoft publié par VIDA sur Source Cooperative (GeoParquet, un fichier
par pays). DuckDB ne lit que les morceaux du fichier qui touchent la zone (le fichier entier fait 836 Mo).

Usage : python telecharger_batiments_google.py
Sortie : donnees/batiments_google_microsoft.geojson
"""

import duckdb
import geopandas as gpd
from shapely import wkb

from config import DONNEES, ZONE_BBOX

URL = ("https://data.source.coop/vida/google-microsoft-open-buildings/geoparquet/"
       "by_country/country_iso=SEN/SEN.parquet")


def main():
    ouest, sud, est, nord = ZONE_BBOX
    con = duckdb.connect()
    con.sql("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    lignes = con.sql(f"""
        SELECT bf_source, confidence, area_in_meters, ST_AsWKB(geometry) AS wkb
        FROM read_parquet('{URL}')
        WHERE bbox.xmin <= {est} AND bbox.xmax >= {ouest} AND bbox.ymin <= {nord} AND bbox.ymax >= {sud}
    """).fetchall()
    gdf = gpd.GeoDataFrame(
        [{"source": s, "confiance": c, "surface_m2": a} for s, c, a, _ in lignes],
        geometry=[wkb.loads(bytes(g)) for *_, g in lignes], crs="EPSG:4326")
    sortie = DONNEES / "batiments_google_microsoft.geojson"
    gdf.to_file(sortie, driver="GeoJSON")
    print(f"{len(gdf)} bâtiments écrits dans {sortie.name}")
    print(gdf.source.value_counts().to_string())


if __name__ == "__main__":
    main()
