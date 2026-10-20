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

from config import ANNEES_PROJECTION, CRS_METRIQUE, CRS_WEB, DONNEES, NIVEAUX_RISQUE, NON_EVALUE, RESULTATS
from exposition import (bandes_menacees, compter_exposition, fusionner_batiments, habitants_par_batiment,
                        marge_avant_batiments, rattacher_quartiers)
from recul import positions_sur_transects, statistiques, traits_projetes
from risque import altitude_cote, classer_risque_global
from transects import construire_transects, ligne_de_base, transects_zone_digue

COULEURS_RISQUE = {"faible": "#2e7d32", "moyen": "#f9a825", "élevé": "#ef6c00", "très élevé": "#c62828",
                   NON_EVALUE: "#9e9e9e"}


def lire_si_present(nom: str):
    chemin = DONNEES / f"{nom}.geojson"
    return gpd.read_file(chemin) if chemin.exists() else None


def exporter(gdf: gpd.GeoDataFrame, nom: str) -> None:
    gdf.to_crs(CRS_WEB).to_file(RESULTATS / f"{nom}.geojson", driver="GeoJSON")


def carte_controle(traits, resultats, projetes, bandes, chemin) -> None:
    fig, ax = plt.subplots(figsize=(7, 11))
    for _, t in traits.sort_values("date").iterrows():
        gpd.GeoSeries([t.geometry], crs=traits.crs).plot(ax=ax, color="#90a4ae", linewidth=0.6)
    for niveau in NIVEAUX_RISQUE + [NON_EVALUE]:
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
    parser.add_argument("--base", help="GeoJSON dont le trait le plus ancien sert de ligne de base "
                                       "(par défaut : --traits ; utile si --traits ne couvre pas toute la côte à sa "
                                       "première date, comme le fichier combiné)")
    args = parser.parse_args()
    RESULTATS.mkdir(exist_ok=True)

    traits = gpd.read_file(args.traits)
    if "date" not in traits.columns:
        raise SystemExit("Le fichier de traits de côte doit avoir une colonne « date ».")
    traits = traits.to_crs(CRS_METRIQUE)
    print(f"{len(traits)} traits de côte, du {traits.date.min()} au {traits.date.max()}")

    base = ligne_de_base(gpd.read_file(args.base).to_crs(CRS_METRIQUE) if args.base else traits)
    transects = construire_transects(base)
    print(f"{len(transects)} transects tous les 50 m sur {base.length / 1000:.1f} km de côte")

    positions = positions_sur_transects(transects, traits)
    resultats = statistiques(transects, positions, zone_digue=transects_zone_digue(transects))
    print(f"{len(resultats)} transects avec au moins 3 mesures")

    batiments = fusionner_batiments(lire_si_present("batiments_osm"), lire_si_present("batiments_google_microsoft"))
    if batiments is not None:
        print(f"{len(batiments)} bâtiments : {batiments.source.value_counts().to_dict()}")
        batiments = habitants_par_batiment(batiments)
    equipements = lire_si_present("equipements_osm")
    resultats = rattacher_quartiers(resultats, lire_si_present("quartiers_osm"), base)

    annee = ANNEES_PROJECTION[0]
    resultats = marge_avant_batiments(resultats, batiments, None)
    bandes_par_annee, batiments_par_annee = {}, {}
    for a in ANNEES_PROJECTION:
        bandes_par_annee[a] = bandes_menacees(resultats, a)
        resultats, batiments_par_annee[a] = compter_exposition(resultats, bandes_par_annee[a], batiments,
                                                               equipements, a)
        resultats = marge_avant_batiments(resultats, batiments, a)
    bandes = bandes_par_annee[annee]
    resultats = classer_risque_global(altitude_cote(resultats), annee)
    projetes = gpd.GeoDataFrame(
        gpd.pd.concat([traits_projetes(resultats, a) for a in ANNEES_PROJECTION], ignore_index=True),
        crs=CRS_METRIQUE)

    exporter(resultats.drop(columns=["nx", "ny", "origine_x", "origine_y"]), "transects_resultats")
    exporter(projetes, "traits_de_cote_projetes")
    for a in ANNEES_PROJECTION:
        exporter(bandes_par_annee[a], f"bande_menacee_{a}")
        exporter(batiments_par_annee[a], f"batiments_menaces_{a}")
    exporter(gpd.GeoDataFrame(geometry=[base], crs=CRS_METRIQUE), "ligne_de_base")
    resultats.drop(columns="geometry").to_csv(RESULTATS / "transects_resultats.csv", index=False, encoding="utf-8-sig")

    resume = (resultats.groupby("quartier", dropna=False)
              .agg(transects=("transect_id", "count"), recul_moyen_m_an=("recul_m_an", "mean"),
                   recul_max_m_an=("recul_m_an", "max"), altitude_mediane_m=("altitude_m", "median"),
                   troncons_non_evalues=("projection_fiable", lambda s: int((~s).sum())),
                   marge_min_actuelle_m=("marge_batiments_actuelle_m", "min"),
                   **{f"marge_min_{a}_m": (f"marge_batiments_{a}_m", "min") for a in ANNEES_PROJECTION},
                   **{f"pire_cas_marge_min_{a}_m": (f"pire_cas_marge_{a}_m", "min") for a in ANNEES_PROJECTION},
                   **{f"{quoi}_menaces_{a}": (f"{quoi}_menaces_{a}", "sum")
                      for a in ANNEES_PROJECTION for quoi in ("batiments", "habitants", "equipements")})
              .round(2).sort_values("recul_moyen_m_an", ascending=False))
    resume.to_csv(RESULTATS / "resume_par_quartier.csv", encoding="utf-8-sig")
    carte_controle(traits, resultats, projetes, bandes, RESULTATS / "carte_controle.png")

    print(f"\nTronçons projetés : {int(resultats.projection_fiable.sum())} ; avec une rupture (zone de la brèche) : "
          f"{int(resultats.rupture.sum())} ; derrière la digue : {int(resultats.zone_digue.sum())} "
          f"(dont non évalués : {int((resultats.zone_digue & ~resultats.projection_fiable).sum())})")
    print(f"Recul moyen : {resultats.recul_m_an.mean():.2f} m/an ; maximum : {resultats.recul_m_an.max():.2f} m/an")
    for a in ANNEES_PROJECTION:
        print(f"D'ici {a} : {int(resultats[f'batiments_menaces_{a}'].sum())} bâtiments, "
              f"{resultats[f'habitants_menaces_{a}'].sum():.0f} habitants, "
              f"{int(resultats[f'equipements_menaces_{a}'].sum())} équipements dans la bande menacée")
    print(f"Tronçons à crête de dune basse (< 3 m) : {int(resultats.cote_basse.sum())} sur {len(resultats)}")
    print("Répartition du risque :", resultats.risque.value_counts().to_dict())
    print(f"\nRésultats écrits dans {RESULTATS}")


if __name__ == "__main__":
    main()
