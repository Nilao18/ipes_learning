#-----------------------------------------------------------------------------------
# Configuration IPES - constantes et etat partage entre modules
#-----------------------------------------------------------------------------------
# Les variables modifiees en cours d'execution (MODE, poi, NIGHT_VISION) sont lues
# via "import hud_config as cfg" puis "cfg.MODE". Ne jamais faire "from hud_config
# import MODE" : la valeur serait copiee et ne suivrait plus les changements.

# Zones HUD -
#---------------------------
#    A |      B     |  C   |
#      |            |      |
#------|------------|------|
#  D   |   CENTRE   |  E   |
#==========================|
#             I            |
#==========================|
#  D   |   CENTRE   |  E   |
#------|------------|------|
#  F   |      G     |  H   |
#      |            |      |
#---------------------------

# Zone A - Infos systeme (heure/date/FPS/latence/ecran droit ou gauche)
# Zone B - Boussole + Altimetre
# Zone C - Navigation GPS + minimap
# Zone D - Alerte cote gauche
# Zone E - Alerte cote droit
# Zone F - Biodata (Frequence cardiaque/SPO2/Temperature corporelle)
# Zone G - Transcription et traduction en temps reel (texte + voix)
# Zone H - Infos environnement (Temperature/humidite/presence gaz)
# Zone I - Bandeau d'alerte central (temporaire)

#----------------------------------------------------------------------------- Affichage elements
DEBUG = False        # True pour afficher FPS/LAT (Zone C) + PITCH/YAW/ROLL (Zone B)
SHOW_RETICULE = True # True pour afficher le reticule central (Zone CENTRE)
SHOW_HORIZON = False # True pour afficher l'horizon artificiel (Zone CENTRE)
SHOW_COMPASS = True  # True pour afficher la boussole (Zone B)
SHOW_ALTITUDE = True # True pour afficher l'altitude (Zone B)
SHOW_GAS_RES = False # True pour afficher la resistance de la mesure de gaz
ACTIVATE_OCR = True  # True pour activer le traitement OCR (Zone G)
SHOW_OCR = True      # True pour afficher le traitement OCR (Zone G)

#----------------------------------------------------------------------------- Chemins
TILES_DIR = "/home/quentin/ipes/maps/tours"  # Repertoire des tuiles minimap

CAM_LEFT  = "/dev/v4l/by-path/platform-3610000.usb-usb-0:1.1:1.0-video-index0"
CAM_RIGHT = "/dev/v4l/by-path/platform-3610000.usb-usb-0:1.4:1.0-video-index0"
CAM_NIGHT = "/dev/v4l/by-path/platform-3610000.usb-usb-0:1.3:1.0-video-index0"

GPS_PORT = '/dev/ttyTHS1'
RADAR_PORT = '/dev/ttyUSB0'

#----------------------------------------------------------------------------- Vision nocturne
NIGHT_VISION = False             # True = camera nocturne active (modifie a l'execution)
NIGHT_VISION_AUTO_SWITCH = False # True = bascule auto apres delai
NIGHT_VISION_DELAY = 10          # secondes avant bascule auto

#----------------------------------------------------------------------------- Geometrie affichage Xreal
ECRAN_W = 1920
ECRAN_H = 1080
MARGE_G = 0.10   # marge gauche (bord flou, IPD superieur aux lunettes)
MARGE_D = 0.05   # marge droite
MARGE_Y = 0.05   # marges haute et basse (troncature)

#----------------------------------------------------------------------------- Modes HUD
MODES = ["NORMAL", "NAV", "MINIMAL", "OFF"]
MODE = "NORMAL"                                  # modifie a l'execution
MINIMAP_SIZE = {"NORMAL": 260, "NAV": 390}       # taille minimap par mode
COMPASS_DIV = {"NORMAL": 2, "NAV": 3}            # diviseur largeur boussole par mode

#----------------------------------------------------------------------------- Verrouillage POI
FOV_H = 40.0                       # champ horizontal Xreal Air 2 Pro (degres)
FOV_V = 22.6                       # champ vertical
PX_PER_DEG_X = ECRAN_W / FOV_H
PX_PER_DEG_Y = ECRAN_H / FOV_V
POI_COLOR = (0, 200, 255)
poi = None                         # {"yaw":, "pitch":, "t":} ou None

#----------------------------------------------------------------------------- Seuils d'alerte
ALERT_DURATION = 1.5      # secondes d'affichage d'une alerte laterale
SEUIL_RES_GAS = 20000     # ohms - sous ce seuil : alerte gaz
SEUIL_TEMP_EXT = 35       # degres C exterieurs
SEUIL_TEMP_JETSON = 75    # degres C SoC
