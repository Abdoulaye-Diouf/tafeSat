"""Paramètres de l'analyse TefesSat (érosion côtière, Langue de Barbarie, Saint-Louis)."""

from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DONNEES = RACINE / "donnees"
RESULTATS = RACINE / "resultats"

# Zone d'étude envoyée à SENSAT (WGS84) : ouest, sud, est, nord
ZONE_BBOX = (-16.58, 15.75, -16.45, 16.08)

# Projection métrique pour tous les calculs (UTM zone 28N couvre Saint-Louis)
CRS_METRIQUE = "EPSG:32628"
CRS_WEB = "EPSG:4326"

# Un point situé en mer, pour savoir de quel côté du trait de côte est l'océan
POINT_EN_MER = (-16.56, 15.95)  # (longitude, latitude)

# Transects
ESPACEMENT_TRANSECTS_M = 50       # un transect tous les 50 m le long de la côte
DEMI_LONGUEUR_TRANSECT_M = 1000   # 1 km de chaque côté : au sud, la côte a reculé de plus de 300 m depuis 2016

# Zone de la brèche : la côte ne recule pas régulièrement, elle « saute » (langue de sable qui disparaît,
# embouchure qui se déplace). Un déplacement de plus de 150 m entre deux dates est une rupture :
# la projection ne prolonge pas le saut, elle utilise seulement les dates après la dernière rupture.
SAUT_RUPTURE_M = 150
# Conditions pour projeter un tronçon (sinon : « non évalué »)
MIN_DATES_PROJECTION = 4
MIN_DUREE_PROJECTION_ANS = 3
ECART_DERNIERE_DATE_MAX_ANS = 1.5  # la dernière mesure doit être récente
SIMPLIFICATION_LIGNE_DE_BASE_M = 100  # lissage de la ligne de base

# Projections
ANNEES_PROJECTION = (2030, 2035)

# Classement du risque selon la vitesse de recul (m/an).
# Seuils provisoires : à ajuster quand on aura les vraies mesures.
SEUILS_RECUL_M_AN = {"moyen": 0.5, "eleve": 1.0, "tres_eleve": 2.0}
NIVEAUX_RISQUE = ["faible", "moyen", "élevé", "très élevé"]
NON_EVALUE = "non évalué"  # série trop courte ou trop ancienne pour projeter

# Le risque final part du niveau donné par la vitesse de recul, puis monte d'un niveau
# si la côte est basse, et d'un autre si beaucoup d'habitants sont exposés.
ALTITUDE_BASSE_M = 3              # crête de dune en dessous de laquelle la côte est jugée basse
# Altitude mesurée sur 200 m côté terre depuis la côte actuelle : le Copernicus DEM date de 2011–2015,
# et la côte a parfois avancé de près de 100 m depuis (Guet N'Dar, après la digue).
LARGEUR_ALTITUDE_M = 200
SEUIL_HABITANTS_EXPOSES = 20      # habitants menacés par tronçon de 50 m au-delà desquels le risque monte

# Quartiers : on ne garde que les lieux OSM proches de la côte (sinon un tronçon prend
# le nom d'un quartier de l'autre côté du fleuve), et au-delà d'une distance, côte non habitée.
QUARTIER_DISTANCE_COTE_MAX_M = 1000
QUARTIER_DISTANCE_TRANSECT_MAX_M = 3000

# Fichiers produits par telecharger_altitude_population.py
FICHIER_ALTITUDE = DONNEES / "altitude_copernicus_dem.tif"
FICHIER_POPULATION = DONNEES / "population_worldpop_2025.tif"

# Bâtiments Google Open Buildings : on garde les détections assez sûres
CONFIANCE_MIN_GOOGLE = 0.70

# Plan de secours si WorldPop manque : habitants par bâtiment (taille moyenne des ménages ANSD)
PERSONNES_PAR_BATIMENT = None
