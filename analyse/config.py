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
DEMI_LONGUEUR_TRANSECT_M = 300    # 300 m côté terre et 300 m côté mer
SIMPLIFICATION_LIGNE_DE_BASE_M = 100  # lissage de la ligne de base

# Projections
ANNEES_PROJECTION = (2030, 2035)

# Classement du risque selon la vitesse de recul (m/an).
# Seuils provisoires : à ajuster quand on aura les vraies mesures.
SEUILS_RECUL_M_AN = {"moyen": 0.5, "eleve": 1.0, "tres_eleve": 2.0}
NIVEAUX_RISQUE = ["faible", "moyen", "élevé", "très élevé"]

# Hypothèse pour estimer les habitants exposés à partir des bâtiments.
# À remplacer par WorldPop ou les chiffres ANSD dès qu'on les a.
PERSONNES_PAR_BATIMENT = None
