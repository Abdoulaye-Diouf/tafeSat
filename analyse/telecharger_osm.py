"""Télécharge depuis OpenStreetMap les bâtiments, les équipements et les noms de quartiers de la zone d'étude.

Usage : python analyse/telecharger_osm.py
Sorties (dans donnees/) : batiments_osm.geojson, equipements_osm.geojson, quartiers_osm.geojson
"""

import sys
import time

import geopandas as gpd
import requests
from shapely.geometry import Point, Polygon

from config import DONNEES, ZONE_BBOX

SERVEURS_OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


def requete_overpass(corps: str, zone: tuple = ZONE_BBOX) -> list:
    ouest, sud, est, nord = zone
    bbox = f"{sud},{ouest},{nord},{est}"
    requete = f"[out:json][timeout:180];({corps.replace('BBOX', bbox)});out geom;"
    derniere_erreur = None
    for tentative in range(2):
        for serveur in SERVEURS_OVERPASS:
            try:
                reponse = requests.post(serveur, data={"data": requete},
                                        headers={"User-Agent": "TefesSat-hackathon-SENSAT"}, timeout=240)
                reponse.raise_for_status()
                return reponse.json()["elements"]
            except (requests.RequestException, ValueError) as erreur:
                print(f"  {serveur} indisponible ({erreur}), essai suivant…", flush=True)
                derniere_erreur = erreur
        time.sleep(20)
    raise requests.RequestException(f"Tous les serveurs Overpass ont échoué : {derniere_erreur}")


def cases(colonnes: int = 3, lignes: int = 6) -> list[tuple]:
    """Découpe la zone en petites cases : une seule requête sur toute la zone est trop lourde."""
    ouest, sud, est, nord = ZONE_BBOX
    dx, dy = (est - ouest) / colonnes, (nord - sud) / lignes
    return [(ouest + i * dx, sud + j * dy, ouest + (i + 1) * dx, sud + (j + 1) * dy)
            for j in range(lignes) for i in range(colonnes)]


def batiments() -> gpd.GeoDataFrame:
    lignes, vus = [], set()
    toutes = cases()
    for n, zone in enumerate(toutes, 1):
        print(f"  case {n}/{len(toutes)}", flush=True)
        for el in requete_overpass('way["building"](BBOX);', zone):
            coords = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
            if el["id"] not in vus and len(coords) >= 4 and coords[0] == coords[-1]:
                vus.add(el["id"])
                lignes.append({"osm_id": el["id"], "type": el["tags"].get("building", "yes"), "geometry": Polygon(coords)})
    return gpd.GeoDataFrame(lignes, geometry="geometry", crs="EPSG:4326")


def equipements() -> gpd.GeoDataFrame:
    corps = ('nwr["amenity"~"^(school|college|kindergarten|place_of_worship|hospital|clinic|doctors|health_post)$"](BBOX);')
    lignes = []
    for el in requete_overpass(corps):
        if el["type"] == "node":
            point = Point(el["lon"], el["lat"])
        elif "bounds" in el:
            b = el["bounds"]
            point = Point((b["minlon"] + b["maxlon"]) / 2, (b["minlat"] + b["maxlat"]) / 2)
        else:
            continue
        tags = el.get("tags", {})
        lignes.append({"osm_id": el["id"], "categorie": tags.get("amenity"), "nom": tags.get("name"), "geometry": point})
    return gpd.GeoDataFrame(lignes, geometry="geometry", crs="EPSG:4326")


def quartiers() -> gpd.GeoDataFrame:
    lignes = []
    for el in requete_overpass('node["place"~"^(suburb|neighbourhood|quarter|village|hamlet)$"](BBOX);'):
        tags = el.get("tags", {})
        if tags.get("name"):
            lignes.append({"nom": tags["name"], "place": tags["place"], "geometry": Point(el["lon"], el["lat"])})
    return gpd.GeoDataFrame(lignes, geometry="geometry", crs="EPSG:4326")


def main() -> None:
    DONNEES.mkdir(exist_ok=True)
    for nom, fonction in [("batiments_osm", batiments), ("equipements_osm", equipements), ("quartiers_osm", quartiers)]:
        print(f"Téléchargement : {nom}…", flush=True)
        try:
            gdf = fonction()
        except requests.RequestException as erreur:
            sys.exit(f"Échec du téléchargement de {nom} : {erreur}")
        gdf.to_file(DONNEES / f"{nom}.geojson", driver="GeoJSON")
        print(f"  {len(gdf)} éléments enregistrés dans donnees/{nom}.geojson")


if __name__ == "__main__":
    main()
