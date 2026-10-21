# TefesSat – analyse du recul de la côte (Langue de Barbarie, Saint-Louis)

Hackathon « Du satellite à la solution » (SENSAT / TRL Space), octobre 2026.
Équipe : Ndèye Fatou SOW (référente), Abdoulaye DIOUF, Malick FALL.

## Ce que fait ce code

À partir de traits de côte datés (extraits des images satellites), la chaîne calcule :

1. une **ligne de base** et **1 003 transects** perpendiculaires à la côte, tous les 50 m, longs de 1 km de chaque côté ;
2. la **position du trait de côte** sur chaque transect, à chaque date ;
3. les **vitesses** : NSM (déplacement net, m), EPR (m/an), LRR (régression linéaire, m/an) et R², comme l'outil DSAS ;
4. les **ruptures** de la zone de la brèche : quand la côte saute de plus de 150 m entre deux dates (langue de sable qui disparaît), la projection ne prolonge pas ce saut et ne part que des dates suivantes ;
5. la **côte projetée en 2030 et 2035** avec une méthode robuste (Theil-Sen) et sa marge d'erreur à 95 % ; un tronçon dont la série est trop courte ou trop ancienne est marqué « non évalué » ;
6. la **bande menacée** en 2030 et 2035, avec les **bâtiments**, les **habitants** et les **équipements** (écoles, lieux de culte, santé) qui s'y trouvent ;
7. la **marge restante** entre la côte projetée et la maison la plus proche, en 2030 et 2035 ;
8. un **niveau de risque** par tronçon : le niveau donné par la vitesse de recul, plus un niveau si la crête de la dune fait moins de 3 m, plus un niveau si 20 habitants ou plus sont exposés.

Convention : une vitesse `lrr_m_an` négative veut dire que la côte recule. La colonne `recul_m_an` (vitesse robuste utilisée pour projeter) est positive quand la côte recule.

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## Utilisation

Tous les scripts se lancent depuis le dossier `analyse/` ou depuis la racine du projet.

**1. Données de contexte** (une seule fois ; les résultats sont dans `donnees/`) :

```bash
python analyse/telecharger_osm.py                     # bâtiments, équipements, quartiers OpenStreetMap
python analyse/telecharger_altitude_population.py     # altitude Copernicus DEM (30 m) et population WorldPop 2025 (100 m)
python analyse/telecharger_batiments_google.py        # bâtiments Google Open Buildings et Microsoft (1 minute, 34 Mo, non versionné)
```

**2. Traits de côte** à partir des images Sentinel-2 (une par an, saison sèche, 2016 à 2025) ; une version CoastSat peut servir de comparaison :

```bash
python analyse/traits_de_cote_sentinel2.py            # -> donnees/traits_de_cote_S2.geojson
```

**3. Analyse complète**, avec les traits de côte combinés : au nord, les 372 traits CoastSat d'Abdoulaye (série dense) ; ailleurs, les nôtres. La ligne de base reste notre trait de côte de 2016, qui couvre toute la côte :

```bash
python analyse/fusion_traits.py                       # -> donnees/traits_de_cote_combines.geojson
python analyse/pipeline.py --traits donnees/traits_de_cote_combines.geojson --base donnees/traits_de_cote_S2.geojson
```

**4. Analyses complémentaires** :

```bash
python analyse/effet_digue.py --traits donnees/traits_de_cote_S2.geojson     # avant / après la digue de Guet Ndar, avec zone témoin
python analyse/verification_sentinel1.py                                     # trait de côte radar comparé à Sentinel-2
python analyse/comparaison_coastsat.py                                       # nos traits de côte comparés à ceux de CoastSat
python analyse/sensibilite.py --traits donnees/traits_de_cote_combines.geojson --base donnees/traits_de_cote_S2.geojson   # les chiffres clés changent-ils si on modifie les réglages ?
```

Pour une nouvelle année ou d'autres traits de côte (CoastSat), on refait seulement l'étape 2, puis on relance les étapes 3 et 4 avec le nouveau fichier : tout le reste se recalcule.

Pour tester sans vraies données : `python analyse/donnees_test.py`, puis
`python analyse/pipeline.py --traits donnees/traits_de_cote_TEST.geojson`.
**Les données de test sont fictives : ne jamais montrer leurs résultats au jury.**

## Format attendu des traits de côte (pour Abdoulaye)

Un fichier GeoJSON avec :
- des **lignes** (LineString ou MultiLineString), en WGS84 ;
- une colonne **`date`** au format `AAAA-MM-JJ` ;
- **uniquement le trait de côte côté océan** (retirer la rive du fleuve si elle est détectée).

C'est le format de CoastSat : `SDS_tools.output_to_gdf(output, 'lines')`, puis `.to_file('traits_de_cote.geojson', driver='GeoJSON')`.
Au moins 4 dates sur 3 ans sont nécessaires pour projeter un tronçon ; idéalement une image peu nuageuse par an, en saison sèche.

## Sorties (dossier `resultats/`, pour le tableau de bord de Malick)

| Fichier | Contenu |
|---|---|
| `transects_resultats.geojson` / `.csv` | un tronçon par ligne : vitesses, rupture, projections et marges d'erreur, risque, altitude, bâtiments, habitants et équipements menacés, marge avant les maisons, quartier |
| `traits_de_cote_projetes.geojson` | côte projetée en 2030 et 2035 (coupée là où un tronçon n'est pas évalué) |
| `bande_menacee_2030.geojson`, `bande_menacee_2035.geojson` | zone que la mer devrait atteindre |
| `batiments_menaces_2030.geojson`, `batiments_menaces_2035.geojson` | bâtiments situés dans cette zone, avec leurs habitants estimés |
| `ligne_de_base.geojson` | ligne de référence des transects |
| `positions_par_annee.csv` | historique de la côte : une ligne par tronçon, une colonne par année (médiane des positions de l'année, m, positive vers la mer) |
| `positions_par_date.csv` | historique complet : une ligne par tronçon et par date (`transect_id`, `date`, `distance_m`) |
| `resume_par_quartier.csv` | par quartier : recul moyen et maximum, altitude, marge minimale, bâtiments, habitants et équipements menacés |
| `effet_digue.csv`, `effet_digue.png` | déplacement de la côte derrière la digue et dans la zone témoin |
| `verification_sentinel1.csv` | écart entre le trait de côte radar et le trait de côte optique |
| `sensibilite.csv` | chiffres clés recalculés en changeant un réglage à la fois |
| `comparaison_coastsat.csv` | écart entre nos traits de côte et ceux de CoastSat, aux dates communes |
| `carte_controle.png` | carte rapide pour vérifier le résultat |

Tous les GeoJSON de sortie sont en WGS84, prêts pour Leaflet.

### Colonnes utiles de `transects_resultats` (pour la fiche d'un tronçon)

| Colonne | Signification |
|---|---|
| `quartier` | quartier OSM côtier le plus proche, ou « Côte non habitée » |
| `recul_m_an` | vitesse robuste ; positive = la côte recule, négative = elle avance |
| `risque` | `faible`, `moyen`, `élevé`, `très élevé` ou `non évalué` |
| `rupture`, `date_rupture` | zone de la brèche : saut de la côte et sa date |
| `zone_digue`, `motif_non_evalue` | zone influencée par la digue (pas de projection : trop peu d'images depuis les travaux), et raison d'un « non évalué » |
| `marge_batiments_actuelle_m` | distance mesurée aujourd'hui entre la côte et la maison la plus proche, sans projection |
| `pire_cas_marge_2030_m` (idem 2035) | marge moins la marge d'erreur ; négative = des maisons pourraient être atteintes dans le pire cas |
| `position_2030_m`, `incertitude_2030_m` (idem 2035) | côte projetée et marge d'erreur |
| `marge_batiments_2030_m` (idem 2035) | distance entre la côte projetée et la maison la plus proche |
| `batiments_menaces_2030`, `habitants_menaces_2030`, `equipements_menaces_2030` (idem 2035) | ce qui est dans la bande menacée |
| `altitude_m`, `cote_basse` | crête de la dune sur 200 m côté terre ; basse si moins de 3 m |

### Version wolof

Les textes du tableau de bord en français et en wolof sont dans `docs/traductions_fr_wo.json` (bouton FR | WO). Le wolof est à corriger par l'équipe avant la démonstration.

## Paramètres (`analyse/config.py`)

Zone d'étude, transects, seuils de rupture, conditions pour projeter, seuils de risque, altitude basse, seuil d'habitants exposés, confiance minimale des bâtiments Google.
Les seuils de risque (0,5 / 1 / 2 m/an) sont des choix de l'équipe : à ajuster avec les utilisateurs (mairie, CSE). L'effet des principaux réglages sur les résultats est mesuré par `analyse/sensibilite.py`.

## Sources de données

- Sentinel-2 L2A et Sentinel-1 RTC (Copernicus) : lus via Microsoft Planetary Computer.
- Altitude : Copernicus DEM GLO-30. Population : WorldPop 2025, 100 m, version contrainte.
- Bâtiments : OpenStreetMap, plus Google Open Buildings et Microsoft (jeu fusionné VIDA, Source Cooperative), confiance ≥ 70 %.

## Limites à connaître

- La projection suppose que la tendance actuelle continue ; elle s'arrête à 2035 et donne toujours une marge d'erreur.
- La précision dépend de la résolution des images (10 m pour Sentinel-2) et de la marée au moment de la prise de vue (non corrigée).
- Le Copernicus DEM date de 2011–2015 et inclut la hauteur des bâtiments.
- Le radar Sentinel-1 n'est fiable que par mer calme : les vagues qui déferlent le trompent.
- Les bâtiments Google peuvent contenir de fausses détections : vérifier sur image ceux qui comptent dans les chiffres présentés.
