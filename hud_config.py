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
#----------------------------------------------------------------------------- Import
import os
#----------------------------------------------------------------------------- Affichage elements
DEBUG = False        # True pour afficher FPS/LAT (Zone C) + PITCH/YAW/ROLL (Zone B)
SHOW_GAS_RES = False # True pour afficher la resistance de la mesure de gaz

#----------------------------------------------------------------------------- Couches
# Chaque element du HUD est une couche activable independamment. Un "mode" n'est
# qu'un jeu de couches nomme (voir PRESETS) : rien n'empeche d'en activer d'autres
# par-dessus, par exemple la navigation ET le cadran sentinelle en meme temps.
COUCHES = ("systeme_detail",   # date, CPU, temperature, GPS dans les donnees systeme
           "boussole",         # Zone B : bande de cap
           "altimetre",        # Zone B : echelle d'altitude (a droite)
           "vitesse",          # Zone B : echelle de vitesse (a gauche)
           "vario",            # Zone B : variometre (a droite de l'altimetre)
           "horizon",          # Zone B : horizon artificiel
           "minimap",          # Zone C : carte
           "reticule",         # Zone CENTRE
           "poi",              # Zone CENTRE : point verrouille
           "radar",            # distance radar + arc du cadran
           "vignettes",        # personnes detectees + retroviseur
           "cadran",           # vue de dessus du mode sentinelle
           "ocr",              # Zone G : lecture de texte
           "environnement",    # Zone H : temperature, humidite, gaz
           "bandes")           # bandes d'alerte laterales et basse

_TOUT = ("systeme_detail", "boussole", "altimetre", "minimap", "reticule", "poi",
         "radar", "vignettes", "ocr", "environnement", "bandes")
# Plus de mode OFF : il faisait doublon avec MINIMAL, et la vraie extinction est
# celle de l'ecran des Xreal (appui long sur le poussoir coude), seule a supprimer
# toute emission lumineuse. MINIMAL n'est plus une position du selecteur mais une
# bascule temporaire : il se superpose au mode courant et le restitue en sortant.
PRESETS = {
    "MINIMAL":    ("vignettes", "bandes"),
    "PILOTAGE":   ("boussole", "altimetre", "vitesse", "vario", "horizon",
                   "reticule", "poi", "bandes"),
    "NORMAL":     _TOUT,
    "NAV":        _TOUT,                                 # minimap plus grande, voir MINIMAP_SIZE
    "SENTINELLE": ("cadran", "radar", "vignettes", "bandes"),
    # Presets personnels, a redefinir librement. CUSTOM1 montre l'interet des couches :
    # la navigation complete AVEC le cadran de surveillance, impossible avant.
    "CUSTOM1":    _TOUT + ("cadran",),
    "CUSTOM2":    _TOUT,
    "CUSTOM3":    ("cadran", "radar", "vignettes", "bandes", "minimap", "boussole"),
    "REGLAGES":   ("systeme_detail",),
}
couches = set(PRESETS["NORMAL"])                         # etat courant, modifie a l'execution

# Touche clavier -> couche basculee. Les couches restent independantes du mode :
# activer le cadran en NAV ne quitte pas le mode NAV.
TOUCHES_COUCHES = {"y": "systeme_detail", "b": "boussole", "a": "altimetre",
                   "h": "horizon",        "l": "minimap",  "x": "reticule",
                   "j": "poi",            "r": "radar",    "p": "vignettes",
                   "k": "cadran",         "g": "ocr",      "e": "environnement",
                   "w": "bandes"}


def actif(nom):
    """True si la couche est affichee. Seul point d'entree : ne jamais tester cfg.MODE."""
    return nom in couches


# Type de vehicule : (libelle, unite, facteur depuis les km/h du GPS, pas de graduation)
# Le GPS donne des km/h ; le facteur convertit, le pas fixe l'echelle du bandeau.
VEHICULES = (("TERRESTRE", "km/h", 1.0,      10),
             ("AERIEN",    "kt",   0.539957,  5),
             ("DRONE",     "m/s",  0.277778,  2))
vehicule = 0                       # index dans VEHICULES, modifie a l'execution

# Variometre, meme index que VEHICULES : (unite, facteur depuis les m/s, demi-plage, pas)
# Au sol la vitesse verticale n'a d'interet qu'en montagne, d'ou une plage etroite.
VARIO_ECHELLE = (("m/s",    1.0,     2.0,  1.0),
                 ("ft/min", 196.85, 2000.0, 500.0),
                 ("m/s",    1.0,     5.0,  1.0))

ALT_UNITE = "M"                    # "M" ou "FT" : unite de l'echelle d'altitude,
                                   # l'autre valeur reste affichee en petit dessous

# Modes editables dans le menu de reglages, dans l'ordre d'affichage
MODES_EDITABLES = ("NORMAL", "NAV", "SENTINELLE", "PILOTAGE",
                   "CUSTOM1", "CUSTOM2", "CUSTOM3", "MINIMAL")

# Couches imposees par un mode : toujours actives, non decochables (grisees au menu).
# C'est ce qui fait qu'un mode reste lui-meme quoi que l'utilisateur ajoute par-dessus.
COUCHES_VERROU = {"NAV":        ("minimap", "boussole"),
                  "SENTINELLE": ("cadran",),
                  "PILOTAGE":   ("boussole", "altimetre", "vitesse", "vario", "horizon")}

# Libelles du menu. Sans accents : les polices Hershey d'OpenCV ne les rendent pas.
LIBELLES = {"systeme_detail": "Donnees systeme", "boussole": "Boussole",
            "altimetre": "Altimetre",           "vitesse": "Vitesse",
            "vario": "Variometre",
            "horizon": "Horizon",
            "minimap": "Minimap",               "reticule": "Reticule",
            "poi": "Point verrouille",          "radar": "Radar",
            "vignettes": "Vignettes",           "cadran": "Cadran sentinelle",
            "ocr": "Lecture de texte",          "environnement": "Environnement",
            "bandes": "Bandes d'alerte"}

PRESETS_FICHIER = os.path.expanduser("~/ipes/presets.json")


def charger_presets():
    """Recharge les presets personnalises enregistres. Silencieux si absent."""
    import json
    try:
        with open(PRESETS_FICHIER, encoding="utf-8") as f:
            for mode, liste in json.load(f).items():
                if mode in PRESETS:
                    PRESETS[mode] = tuple(c for c in liste if c in COUCHES)
        print("Presets charges depuis", PRESETS_FICHIER)
    except FileNotFoundError:
        pass
    except Exception as e:
        print("Presets illisibles (%s), valeurs d'usine conservees" % e)


def sauver_presets():
    import json
    try:
        os.makedirs(os.path.dirname(PRESETS_FICHIER), exist_ok=True)
        with open(PRESETS_FICHIER, "w", encoding="utf-8") as f:
            json.dump({m: sorted(PRESETS[m]) for m in MODES_EDITABLES}, f, indent=1)
        return True
    except Exception as e:
        print("Ecriture des presets impossible :", e)
        return False


def appliquer_mode(mode):
    """Charge le preset d'un mode. Les couches restent modifiables ensuite."""
    global couches
    couches = set(PRESETS.get(mode, ()))

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
BRASSARD_BOUTONS = ("t1", "t2", "t3", "coude", "enc", "rot")   # ordre des bits du masque btn
APPUI_LONG = 0.5                   # s : au-dela, l'appui est long
APPUI_TRES_LONG = 2.0              # s : au-dela, bascule du mode MINIMAL
BOUTON_MINIMAL = "rot"             # seul bouton habilite : trop facile de se tromper
# Position du rotatif -> mode. La position 5 est le cran HAUT du selecteur ;
# on part de la et on progresse dans le sens horaire. OFF n'est plus une position :
# il s'obtient par un appui de 4 s sur le poussoir central (voir APPUI_TRES_LONG).
ROT_MODES = {5: "NORMAL",  6: "NAV",     7: "SENTINELLE", 8: "CUSTOM1",
             1: "CUSTOM2", 2: "CUSTOM3", 3: "REGLAGES",   4: "PILOTAGE"}
CAPTURES = os.path.expanduser("~/ipes/captures")   # images + telemetrie de la touche CAPTURE
VISIERE_NIVEAUX = 3                # niveaux d'assombrissement electrochromique
# Etiquettes des trois touches contextuelles, affichees plus tard sur l'ecran brassard
TOUCHES = {"PILOTAGE":   ("CAPTURE", "POI", "VEHICULE"),
           "CUSTOM1":    ("CAPTURE", "POI", "CAMERA"),
           "CUSTOM2":    ("CAPTURE", "POI", "CAMERA"),
           "CUSTOM3":    ("CAPTURE", "POI", "CAMERA"),
           "REGLAGES":   ("", "", ""),
           "NORMAL":     ("CAPTURE", "POI", "CAMERA"),
           "NAV":        ("CAPTURE", "POI", "MARQUEUR"),
           "SENTINELLE": ("CAPTURE", "POI", "CAMERA"),
           "MINIMAL":    ("CAPTURE", "POI", "")}

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
MODES = ["NORMAL", "NAV", "MINIMAL", "PILOTAGE", "SENTINELLE"]   # raccourcis clavier 1 a 5
MODE = "NORMAL"                                  # modifie a l'execution
MINIMAP_SIZE = {"NORMAL": 260, "NAV": 390}       # taille minimap par mode (defaut 260)
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
CAM_RECO = 2.0            # s entre deux tentatives de reouverture d'une camera
ALERT_STRIPE = 12         # largeur d'une rayure diagonale (px)
DETECT_PERIOD = 0.25      # s entre deux inferences, alternees G/D (0.25 = 2 Hz par cote)
CAM_PERIOD = 0.5          # s entre deux captures OV9281 (0.5 = 2 images/s)
OCR_EVERY = 60            # analyse OCR toutes les N images du HUD
SEUIL_RES_GAS = 20000     # ohms - sous ce seuil : alerte gaz
GAZ_PERIODE = 2.0         # s entre deux mesures de gaz : le chauffage du BME688 est
                          #     coupe le reste du temps. Mesure : il multipliait par 27
                          #     la derive de pression et faussait la temperature
VARIO_FENETRE = 2.0       # s : duree de la regression. Mesure : bruit 0.0043 hPa (3.6 cm)
                          #     a 4 Hz -> +/-0.02 m/s sur 2 s, pour 1 s de latence
VARIO_STAB = 60           # s : la pression derive fortement les 40 premieres secondes
BME_CHAUFFE = 180         # s : la resistance chauffante du BME688 doit se stabiliser
                          #     avant toute mesure de gaz exploitable
SEUIL_TEMP_EXT = 35       # degres C exterieurs
SEUIL_TEMP_JETSON = 75    # degres C SoC
