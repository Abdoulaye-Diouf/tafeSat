"""Analyse de sensibilité : les chiffres clés changent-ils si on modifie les réglages de la méthode ?

On change un réglage à la fois autour de la valeur de référence (config.py) et on recalcule :
le nombre de tronçons projetés, la marge mer – maisons en 2035 à Hydrobase et à Tassinère,
les bâtiments et habitants menacés d'ici 2035, et le nombre de tronçons à dune basse.
Les traits de côte eux-mêmes ne changent pas (le seuil d'Otsu est calculé sur chaque image).

Usage : python sensibilite.py --traits donnees/traits_de_cote_S2.geojson
Sortie : resultats/sensibilite.csv
"""

import argparse

import geopandas as gpd
import pandas as pd

import config
import exposition
import recul
import risque
from exposition import (bandes_menacees, compter_exposition, fusionner_batiments, habitants_par_batiment,
                        marge_avant_batiments, rattacher_quartiers)
from recul import positions_sur_transects, statistiques
from risque import altitude_cote, classer_risque_global
from transects import construire_transects, ligne_de_base, transects_zone_digue

ANNEE = 2035
# Réglage -> (module(s) où il est utilisé, valeurs testées) ; la valeur de référence est celle de config.py
REGLAGES = {
    "SAUT_RUPTURE_M": ([recul], [100, 150, 200]),
    "MIN_DATES_PROJECTION": ([recul], [3, 4, 5]),
    "LARGEUR_ALTITUDE_M": ([risque], [100, 200, 300]),
    "CONFIANCE_MIN_GOOGLE": ([exposition], [0.65, 0.70, 0.80]),
}


def lire(nom):
    chemin = config.DONNEES / f"{nom}.geojson"
    return gpd.read_file(chemin) if chemin.exists() else None


def chiffres_cles(transects, positions, base, osm, google, equipements, quartiers):
    resultats = statistiques(transects, positions, zone_digue=transects_zone_digue(transects))
    resultats = rattacher_quartiers(resultats, quartiers, base)
    batiments = habitants_par_batiment(fusionner_batiments(osm, google))
    bandes = bandes_menacees(resultats, ANNEE)
    resultats, _ = compter_exposition(resultats, bandes, batiments, equipements, ANNEE)
    resultats = marge_avant_batiments(resultats, batiments, ANNEE)
    resultats = classer_risque_global(altitude_cote(resultats), ANNEE)

    def minimum(quartier, colonne):
        return resultats[resultats.quartier == quartier][colonne].min()

    return {"troncons_projetes": int(resultats.projection_fiable.sum()),
            "troncons_non_evalues": int((~resultats.projection_fiable).sum()),
            f"marge_{ANNEE}_hydrobase_m": minimum("Hydrobase", f"marge_batiments_{ANNEE}_m"),
            f"marge_{ANNEE}_tassinere_m": minimum("Tassinère", f"marge_batiments_{ANNEE}_m"),
            f"pire_cas_{ANNEE}_hydrobase_m": minimum("Hydrobase", f"pire_cas_marge_{ANNEE}_m"),
            f"batiments_menaces_{ANNEE}": int(resultats[f"batiments_menaces_{ANNEE}"].sum()),
            f"habitants_menaces_{ANNEE}": round(float(resultats[f"habitants_menaces_{ANNEE}"].sum())),
            "troncons_dune_basse": int(resultats.cote_basse.sum())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--traits", required=True)
    args = parser.parse_args()

    traits = gpd.read_file(args.traits).to_crs(config.CRS_METRIQUE)
    base = ligne_de_base(traits)
    transects = construire_transects(base)
    print("Mesure des positions sur les transects (une seule fois)…", flush=True)
    positions = positions_sur_transects(transects, traits)
    donnees = dict(osm=lire("batiments_osm"), google=lire("batiments_google_microsoft"),
                   equipements=lire("equipements_osm"), quartiers=lire("quartiers_osm"))

    lignes = []
    reference = chiffres_cles(transects, positions, base, **donnees)
    lignes.append({"reglage": "référence", "valeur": "config.py", **reference})
    for nom, (modules, valeurs) in REGLAGES.items():
        valeur_ref = getattr(config, nom)
        for valeur in valeurs:
            if valeur == valeur_ref:
                continue
            for m in modules:
                setattr(m, nom, valeur)
            print(f"{nom} = {valeur}", flush=True)
            lignes.append({"reglage": nom, "valeur": valeur, **chiffres_cles(transects, positions, base, **donnees)})
            for m in modules:
                setattr(m, nom, valeur_ref)

    tableau = pd.DataFrame(lignes)
    config.RESULTATS.mkdir(exist_ok=True)
    tableau.to_csv(config.RESULTATS / "sensibilite.csv", index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 200)
    print("\n" + tableau.to_string(index=False))


if __name__ == "__main__":
    main()
