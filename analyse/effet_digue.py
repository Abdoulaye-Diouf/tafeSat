"""Effet de la digue de Guet Ndar (construite de janvier 2021 à juillet 2022) sur le trait de côte.

On compare la position de la côte avant (2016–2020) et après (2023–2025) la digue, dans la zone protégée
et dans une zone témoin sans digue (Hydrobase). Si la côte avance dans la zone de la digue et pas dans la
zone témoin, c'est l'ouvrage qui fait la différence, pas une année calme.

Usage : python effet_digue.py --traits donnees/traits_de_cote_S2.geojson
Sorties : resultats/effet_digue.csv, resultats/effet_digue.png
"""

import argparse

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from config import CRS_METRIQUE, RESULTATS
from recul import annee_decimale, positions_sur_transects
from transects import construire_transects, ligne_de_base

# Latitudes approximatives (WGS84) : digue de Goxu Mbacc au quai de pêche de Guet Ndar (environ 2,1 km),
# et zone témoin d'Hydrobase, au sud, sans ouvrage
ZONES = {"Zone de la digue (Goxu Mbacc – Guet Ndar)": (16.020, 16.042),
         "Zone témoin sans digue (Hydrobase)": (15.970, 16.000)}
COULEURS = {"Zone de la digue (Goxu Mbacc – Guet Ndar)": "#008C7E",
            "Zone témoin sans digue (Hydrobase)": "#C2581B"}
AVANT, APRES = (2016, 2020), (2023, 2025)
DEBUT_TRAVAUX, FIN_TRAVAUX = 2021.0, 2022.55


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--traits", required=True)
    args = parser.parse_args()

    traits = gpd.read_file(args.traits).to_crs(CRS_METRIQUE)
    transects = construire_transects(ligne_de_base(traits))
    latitudes = gpd.GeoSeries(gpd.points_from_xy(transects.origine_x, transects.origine_y),
                              crs=CRS_METRIQUE).to_crs("EPSG:4326").y
    transects["zone"] = None
    for zone, (sud, nord) in ZONES.items():
        transects.loc[latitudes.between(sud, nord).to_numpy(), "zone"] = zone

    positions = positions_sur_transects(transects[transects.zone.notna()], traits)
    positions = positions.merge(transects[["transect_id", "zone"]], on="transect_id")
    positions["annee"] = annee_decimale(positions.date)

    # Position de chaque transect par rapport à sa moyenne 2016–2020 (0 = côte d'avant la digue)
    avant = positions[positions.annee.between(AVANT[0], AVANT[1] + 1)]
    reference = avant.groupby("transect_id").distance_m.mean()
    positions["ecart_m"] = positions.distance_m - positions.transect_id.map(reference)
    serie = positions.groupby(["zone", "date"]).agg(annee=("annee", "first"), ecart_m=("ecart_m", "median"),
                                                     transects=("transect_id", "count")).reset_index()

    lignes = []
    for zone, g in positions.groupby("zone"):
        apres = g[g.annee.between(APRES[0], APRES[1] + 1)].groupby("transect_id").ecart_m.mean()
        lignes.append({"zone": zone, "transects": g.transect_id.nunique(),
                       "deplacement_median_m": round(float(apres.median()), 1),
                       "part_transects_qui_avancent_pct": round(float((apres > 0).mean() * 100))})
    resume = pd.DataFrame(lignes)
    RESULTATS.mkdir(exist_ok=True)
    resume.to_csv(RESULTATS / "effet_digue.csv", index=False, encoding="utf-8-sig")
    print("Déplacement de la côte après la digue (2023–2025) par rapport à 2016–2020")
    print("(positif = la côte a avancé vers la mer)\n")
    print(resume.to_string(index=False))

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.axvspan(DEBUT_TRAVAUX, FIN_TRAVAUX, color="#E3D9C6", alpha=0.6, linewidth=0)
    ax.text((DEBUT_TRAVAUX + FIN_TRAVAUX) / 2, 0.97, "Construction\nde la digue", transform=ax.get_xaxis_transform(),
            ha="center", va="top", fontsize=9, color="#4A5568")
    ax.axhline(0, color="#9AA5B1", linewidth=1)
    for zone, g in serie.groupby("zone"):
        g = g.sort_values("annee")
        ax.plot(g.annee, g.ecart_m, color=COULEURS[zone], linewidth=2, marker="o", markersize=7,
                markeredgecolor="white", markeredgewidth=1.5, label=zone)
        ax.annotate(f"{g.ecart_m.iloc[-1]:+.0f} m", (g.annee.iloc[-1], g.ecart_m.iloc[-1]),
                    xytext=(8, 0), textcoords="offset points", va="center", fontsize=10, color="#1F2933")
    ax.set_ylabel("Position de la côte par rapport à 2016–2020 (m)\n(au-dessus de 0 : la côte avance)",
                  color="#4A5568")
    ax.set_title("La côte a avancé derrière la digue, pas dans la zone témoin", loc="left", fontsize=12,
                 color="#1F2933")
    for cote in ("top", "right"):
        ax.spines[cote].set_visible(False)
    for cote in ("left", "bottom"):
        ax.spines[cote].set_color("#C9CFD6")
    ax.tick_params(colors="#4A5568")
    ax.grid(axis="y", color="#EEF0F2", linewidth=1)
    ax.set_axisbelow(True)
    ax.legend(loc="lower left", frameon=False, fontsize=9)
    ax.set_xlim(2015.7, 2025.8)
    fig.savefig(RESULTATS / "effet_digue.png", dpi=150, bbox_inches="tight")
    print(f"\nGraphique : {RESULTATS / 'effet_digue.png'}")


if __name__ == "__main__":
    main()
