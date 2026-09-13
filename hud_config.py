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
SHOW_RETICULE = True # reticule central (Zone CENTRE) - touche X, modifie a l'execution
SHOW_HORIZON = False # horizon artificiel (Zone CENTRE) - touche H, modifie a l'execution
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
CAM_BACK  = "/dev/v4l/by-path/platform-3610000.usb-usb-0:2.3:1.0-video-index0"   # OV9281 arriere, USB-A 4 Jetson
ACTIVE_CAM_BACK = False   # bus USB 2.0 sature par 2 OV9281 en MJPG : en attente d un second bus USB

GPS_PORT = '/dev/serial/by-path/platform-3610000.usb-usb-0:2.4:1.0-port0'  # FT232 USB-A
RADAR_PORT = '/dev/serial/by-path/platform-3610000.usb-usb-0:2.1:1.0-port0'  # FT232 USB-A
SERIE_RECO = 2.0                   # s entre deux tentatives de reconnexion GPS/radar
CASQUE_PORT = '/dev/ttyTHS1'       # ESP32-S3 casque, connecteur 40 broches pins 8/10
CASQUE_BAUD = 115200
CASQUE_TIMEOUT = 1.0               # s sans trame IMU avant de declarer la liaison perdue
CASQUE_ACK = 0.5                   # s d'attente d'un accuse de commande
BRASSARD_TIMEOUT = 3.0             # s sans trame brassard avant de le declarer absent

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
NET_G = 110      # debut de la zone nette a gauche, en px depuis le bord gauche de la zone utile

#----------------------------------------------------------------------------- Modes HUD
MODES = ["NORMAL", "NAV", "MINIMAL", "OFF", "SENTINELLE"]
MODES_COMPLETS = ("NORMAL", "NAV")               # modes avec toutes les donnees (les autres = base minimale)
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

#----------------------------------------------------------------------------- Radar
RADAR_FOV = 120.0                  # ouverture azimutale LD2450 (degres)
RADAR_ON = True                    # affichage radar (touche R, modifie a l'execution)

#----------------------------------------------------------------------------- Mode SENTINELLE
SENTINELLE_R = 110                 # rayon du cadran (px)
SENTINELLE_PORTEE = 6.0            # distance representee au bord du cadran (m)
CAM_W, CAM_H = 1280, 720           # resolution de capture des OV9281 (CameraThread)
CAM_FX = 906.0                     # focale en px (calibration K_ov9281, 1280x800)
CAM_HFOV = 70.0                    # champ horizontal = 2*atan(640/906)
TAILLE_PERSONNE = 1.7              # hauteur supposee d'une personne debout (m)
RATIO_ENTIER = 2.5                 # hauteur/largeur mini d une personne entiere (debout ~3.0, jambes masquees ~2.3)

#----------------------------------------------------------------------------- Seuils d'alerte
ALERT_DURATION = 1.5      # secondes d'affichage d'une alerte laterale
ALERT_BAR_W = 12          # largeur des bandes d'alerte laterales (px)
ALERT_BAR_GAP = 20        # ecart entre bande et bord de la zone utile (px)
COL_G = NET_G + ALERT_BAR_W + ALERT_BAR_GAP  # colonne de contenu gauche, apres la bande
ALERT_BAS_MARGE = True    # bande arriere dans la marge basse (False : bord bas de la zone utile)
RETRO_Y = 230             # haut de la vignette retroviseur, sous la boussole (px zone utile)
CAM_FRAICHEUR = 3.0       # s : image plus ancienne = camera consideree indisponible
ALERT_STRIPE = 12         # largeur d'une rayure diagonale (px)
DETECT_PERIOD = 0.25      # s entre deux inferences, alternees G/D (0.25 = 2 Hz par cote)
CAM_PERIOD = 0.5          # s entre deux captures OV9281 (0.5 = 2 images/s)
OCR_EVERY = 60            # analyse OCR toutes les N images du HUD
SEUIL_RES_GAS = 20000     # ohms - sous ce seuil : alerte gaz
SEUIL_TEMP_EXT = 35       # degres C exterieurs
SEUIL_TEMP_JETSON = 75    # degres C SoC
