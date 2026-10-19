# TefesSat – analyse du recul de la côte (Langue de Barbarie, Saint-Louis)

Hackathon national « Du satellite à la solution » (SENSAT / TRL), octobre 2026.
Équipe : Ndèye Fatou SOW (référente), Abdoulaye DIOUF, Malick FALL.

## Ce que fait ce code

À partir de traits de côte datés (extraits des images satellites), la chaîne calcule :

1. une **ligne de base** et des **transects** perpendiculaires à la côte, tous les 50 m ;
2. la **position du trait de côte** sur chaque transect, à chaque date ;
3. les **vitesses de recul** : NSM (déplacement net, m), EPR (m/an), LRR (régression linéaire, m/an) et R² ;
4. la **côte projetée en 2030 et 2035**, avec une marge d'incertitude ;
5. la **bande menacée d'ici 2030** et les **bâtiments et équipements** (écoles, lieux de culte, santé) qui s'y trouvent ;
6. un **niveau de risque** par tronçon de 50 m (faible, moyen, élevé, très élevé).

Convention : une vitesse `lrr_m_an` négative veut dire que la côte recule. La colonne `recul_m_an` donne la même valeur en positif, plus simple à lire.

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## Utilisation

```bash
cd analyse
python telecharger_osm.py                                  # bâtiments, équipements, quartiers (OpenStreetMap)
python pipeline.py --traits ../donnees/traits_de_cote.geojson
```

Pour tester sans vraies données : `python donnees_test.py`, puis
`python pipeline.py --traits ../donnees/traits_de_cote_TEST.geojson`.
**Les données de test sont fictives : ne jamais montrer leurs résultats au jury.**

## Format attendu des traits de côte (pour Abdoulaye)

Un fichier GeoJSON avec :
- des **lignes** (LineString ou MultiLineString), en WGS84 ;
- une colonne **`date`** au format `AAAA-MM-JJ` ;
- **uniquement le trait de côte côté océan** (retirer la rive du fleuve si elle est détectée).

C'est le format de CoastSat : `SDS_tools.output_to_gdf(output, 'lines')`, puis `.to_file('traits_de_cote.geojson', driver='GeoJSON')`.
Au moins 3 dates sont nécessaires ; idéalement une image peu nuageuse par an, en saison sèche.

## Sorties (dossier `resultats/`, pour le tableau de bord de Malick)

| Fichier | Contenu |
|---|---|
| `transects_resultats.geojson` / `.csv` | un transect par ligne : vitesses, projections, risque, bâtiments menacés, quartier |
| `traits_de_cote_projetes.geojson` | côte projetée en 2030 et 2035 |
| `bande_menacee_2030.geojson` | zone que la mer devrait atteindre d'ici 2030 |
| `batiments_menaces_2030.geojson` | bâtiments situés dans cette zone |
| `ligne_de_base.geojson` | ligne de référence des transects |
| `resume_par_quartier.csv` | recul moyen et maximum, bâtiments menacés par quartier |
| `carte_controle.png` | carte rapide pour vérifier le résultat |

Tous les GeoJSON de sortie sont en WGS84, prêts pour Leaflet.

## Paramètres (`analyse/config.py`)

Zone d'étude, espacement des transects, années de projection, seuils de risque.
Les seuils de risque (0,5 / 1 / 2 m/an) sont **provisoires** : à ajuster après les premiers résultats réels.
`PERSONNES_PAR_BATIMENT` permet d'estimer les habitants exposés ; à remplir seulement avec une source fiable (ANSD, WorldPop).

## Limites à connaître

- La projection suppose que le recul continue au même rythme (extrapolation linéaire).
- La précision dépend de la résolution des images (10 m pour Sentinel-2) et de la marée au moment de la prise de vue.
- OpenStreetMap peut ne pas contenir tous les bâtiments ; à compléter avec Google Open Buildings si besoin.
