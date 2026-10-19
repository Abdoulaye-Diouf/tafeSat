"""Chaîne complète : traits de côte datés -> transects -> vitesses de recul -> projections -> exposition.

Usage :
    python analyse/pipeline.py --traits donnees/traits_de_cote.geojson

Le fichier de traits de côte doit contenir des lignes (LineString ou MultiLineString)
et une colonne « date » (format AAAA-MM-JJ). C'est le format produit par CoastSat
(fonction SDS_tools.output_to_gdf, puis export en GeoJSON).

Les bâtiments, équipements et quartiers OSM sont lus dans donnees/ s'ils existent
(lancer d'abord analyse/telecharger_osm.py).
"""

import argparse

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import ANNEES_PROJECTION, CRS_METRIQUE, CRS_WEB, DONNEES, NIVEAUX_RISQUE, RESULTATS
from exposition import bandes_menacees, compter_exposition, rattacher_quartiers
from recul import positions_sur_transects, statistiques, traits_projetes
from transects import construire_transects, ligne_de_base

COULEURS_RISQUE = {"faible": "#2e7d32", "moyen": "#f9a825", "élevé": "#ef6c00", "très élevé": "#c62828"}


def lire_si_present(nom: str):
    chemin = DONNEES / f"{nom}.geojson"
    return gpd.read_file(chemin) if chemin.exists() else None


def exporter(gdf: gpd.GeoDataFrame, nom: str) -> None:
    gdf.to_crs(CRS_WEB).to_file(RESULTATS / f"{nom}.geojson", driver="GeoJSON")


def carte_controle(traits, resultats, projetes, bandes, chemin) -> None:
    fig, ax = plt.subplots(figsize=(7, 11))
    for _, t in traits.sort_values("date").iterrows():
        gpd.GeoSeries([t.geometry], crs=traits.crs).plot(ax=ax, color="#90a4ae", linewidth=0.6)
    for niveau in NIVEAUX_RISQUE:
        sel = resultats[resultats.risque == niveau]
        if len(sel):
            sel.plot(ax=ax, color=COULEURS_RISQUE[niveau], linewidth=1.2, label=f"Risque {niveau}")
    if len(bandes):
        bandes.plot(ax=ax, color="#c62828", alpha=0.35)
    if len(projetes):
        projetes.plot(ax=ax, color="black", linestyle="--", linewidth=1, label=f"Côte projetée {ANNEES_PROJECTION[0]}")
    ax.set_title("TefesSat – vitesses de recul et côte projetée")
    ax.legend(loc="lower left", fontsize=8)
    ax.set_axis_off()
    fig.savefig(chemin, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--traits", required=True, help="GeoJSON des traits de côte datés")
    args = parser.parse_args()
    RESULTATS.mkdir(exist_ok=True)

    traits = gpd.read_file(args.traits)
    if "date" not in traits.columns:
        raise SystemExit("Le fichier de traits de côte doit avoir une colonne « date ».")
    traits = traits.to_crs(CRS_METRIQUE)
    print(f"{len(traits)} traits de côte, du {traits.date.min()} au {traits.date.max()}")

    base = ligne_de_base(traits)
    transects = construire_transects(base)
    print(f"{len(transects)} transects tous les 50 m sur {base.length / 1000:.1f} km de côte")

    positions = positions_sur_transects(transects, traits)
    resultats = statistiques(transects, positions)
    print(f"{len(resultats)} transects avec au moins 3 mesures")

    batiments = lire_si_present("batiments_osm")
    equipements = lire_si_present("equipements_osm")
    resultats = rattacher_quartiers(resultats, lire_si_present("quartiers_osm"))

    annee = ANNEES_PROJECTION[0]
    bandes = bandes_menacees(resultats, annee)
    resultats, batiments_menaces = compter_exposition(resultats, bandes, batiments, equipements, annee)
    projetes = gpd.GeoDataFrame(
        gpd.pd.concat([traits_projetes(resultats, a) for a in ANNEES_PROJECTION], ignore_index=True),
        crs=CRS_METRIQUE)

    exporter(resultats.drop(columns=["nx", "ny", "origine_x", "origine_y"]), "transects_resultats")
    exporter(projetes, "traits_de_cote_projetes")
    exporter(bandes, f"bande_menacee_{annee}")
    exporter(batiments_menaces, f"batiments_menaces_{annee}")
    exporter(gpd.GeoDataFrame(geometry=[base], crs=CRS_METRIQUE), "ligne_de_base")
    resultats.drop(columns="geometry").to_csv(RESULTATS / "transects_resultats.csv", index=False, encoding="utf-8-sig")

    resume = (resultats.groupby("quartier", dropna=False)
              .agg(transects=("transect_id", "count"), recul_moyen_m_an=("recul_m_an", "mean"),
                   recul_max_m_an=("recul_m_an", "max"), **{f"batiments_menaces_{annee}": (f"batiments_menaces_{annee}", "sum")},
                   **{f"equipements_menaces_{annee}": (f"equipements_menaces_{annee}", "sum")})
              .round(2).sort_values("recul_moyen_m_an", ascending=False))
    resume.to_csv(RESULTATS / "resume_par_quartier.csv", encoding="utf-8-sig")
    carte_controle(traits, resultats, projetes, bandes, RESULTATS / "carte_controle.png")

    print(f"\nRecul moyen : {resultats.recul_m_an.mean():.2f} m/an ; maximum : {resultats.recul_m_an.max():.2f} m/an")
    print(f"Bâtiments dans la bande menacée d'ici {annee} : {int(resultats[f'batiments_menaces_{annee}'].sum())}")
    print("Répartition du risque :", resultats.risque.value_counts().to_dict())
    print(f"\nRésultats écrits dans {RESULTATS}")


if __name__ == "__main__":
    main()
