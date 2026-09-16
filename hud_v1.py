#-----------------------------------------------------------------------------------
# IPES HUD V1 - Boucle principale
#-----------------------------------------------------------------------------------
# Architecture :
#   hud_config.py   constantes et etat partage (MODE, poi, NIGHT_VISION)
#   sensors.py      threads IMU, BME688, GPS, radar, cameras, clavier
#   hud_draw.py     rendu des zones, boussole, minimap, POI
#   ocr_process.py  OCR en processus separe
#   person_detect.py detection de personnes YOLOv8n-person en processus separe
#
# Touches (terminal SSH, valider par Entree) :
#   q  quitter          n  bascule vision nocturne     s  capture ecran
#   1-5 mode direct     m  mode suivant                (5 = SENTINELLE)
#   v  verrouiller POI  c  effacer POI
#   i  etat des couches
#   couches : y systeme  b boussole  a altimetre  h horizon  l minimap  x reticule
#             j poi      r radar     p vignettes   k cadran   g ocr     e environnement
#             w bandes
# Brassard : rotatif = mode | t1-t3 = touches contextuelles | coude = visiere
#            tres long (>2 s) sur n'importe quel bouton = extinction totale
import json
import os
import time
from datetime import datetime

import cv2
import numpy as np
import psutil

import hud_config as cfg
from sensors import (CasqueThread, BMEThread, GPSThread, RadarThread,
                     CameraThread, KeyboardThread)
from ocr_process import OCRProcess
from person_detect import PersonDetector
import hud_draw as draw


#----------------------------------------------------------------------------- Instanciations
cam_left = CameraThread(cfg.CAM_LEFT, period=cfg.CAM_PERIOD)
time.sleep(1)
cam_right = CameraThread(cfg.CAM_RIGHT, period=cfg.CAM_PERIOD)
time.sleep(1)
cam_back = (CameraThread(cfg.CAM_BACK, period=cfg.CAM_PERIOD)   # voir ACTIVE_CAM_BACK
            if cfg.ACTIVE_CAM_BACK else None)
time.sleep(1)
cam_night = None

casque = CasqueThread()
time.sleep(0.5)
bme = BMEThread()
time.sleep(0.5)
ocr = OCRProcess()
time.sleep(0.5)
gps = GPSThread()
time.sleep(1)
radar = RadarThread()
kb = KeyboardThread()

print("Init detection personnes...")
detector = PersonDetector()
detect_last = 0.0
detect_side = 'L'
print("Detection OK")

#----------------------------------------------------------------------------- Initialisation
count = 0
fps = 0
rot_precedent = None       # derniere position du rotatif vue, pour n'agir qu'au changement
visiere = 0                # niveau electrochromique suppose (le bouton ne se relit pas)
marqueurs = []             # points poses en mode NAV


def basculer(couche):
    """Active ou desactive une couche, sans toucher au mode courant."""
    if couche in cfg.couches:
        cfg.couches.discard(couche)
    else:
        cfg.couches.add(couche)
    print("Couche %s : %s" % (couche, "ON" if cfg.actif(couche) else "OFF"))


def capturer(image, casque, gps, bme):
    """Image du HUD + telemetrie, horodatees. Action instantanee : elle ne se differe pas."""
    os.makedirs(cfg.CAPTURES, exist_ok=True)
    nom = datetime.now().strftime("%Y%m%d_%H%M%S")
    cv2.imwrite(os.path.join(cfg.CAPTURES, nom + ".png"), image)
    with open(os.path.join(cfg.CAPTURES, nom + ".json"), "w") as f:
        json.dump({"mode": cfg.MODE, "yaw": casque.yaw, "pitch": casque.pitch,
                   "roll": casque.roll, "lat": gps.lat, "lon": gps.lon,
                   "sat": gps.satellites, "fix": gps.fix,
                   "temp": bme.temperature, "hum": bme.humidity}, f, indent=1)
    print("  Capture", nom)
lat_display = 0

alert_l_time = 0
alert_r_time = 0
alert_b_time = 0

jetson_temp = 0.0
cpu_percent = 0.0
sys_update = time.time()

minimap_cache = None
minimap_last_lat = 0
minimap_last_lon = 0

t0 = time.time()
night_switch_time = 0

cv2.namedWindow("IPES HUD V1", cv2.WINDOW_NORMAL)
cv2.setWindowProperty("IPES HUD V1", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
cv2.resizeWindow("IPES HUD V1", cfg.ECRAN_W, cfg.ECRAN_H)

# Curseur souris masque via XFixes : le serveur X le reaffiche seul a la
# deconnexion du client, donc meme en cas de crash du HUD
try:
    from Xlib import display as xdisplay
    xdisp = xdisplay.Display()
    xdisp.xfixes_query_version()
    xdisp.screen().root.xfixes_hide_cursor()
    xdisp.sync()
except Exception as e:
    xdisp = None
    print("Curseur non masque :", e)

# ----------------------------------------------------------------------------- Boucle While
while True:
    # Telemetrie systeme toutes les 2 s
    if time.time() - sys_update > 2.0:
        try:
            with open('/sys/devices/virtual/thermal/thermal_zone1/temp') as f:
                jetson_temp = int(f.read().strip()) / 1000
            cpu_percent = psutil.cpu_percent()
        except Exception:
            pass
        sys_update = time.time()

    # Bascule nocturne automatique
    if cfg.NIGHT_VISION_AUTO_SWITCH and not cfg.NIGHT_VISION:
        if time.time() - t0 > cfg.NIGHT_VISION_DELAY:
            if night_switch_time == 0:
                cam_left.stop()
                cam_right.stop()
                night_switch_time = time.time()
                print("Arret cameras stereo...")
            elif time.time() - night_switch_time > 1.0 and cam_night is None:
                cam_night = CameraThread(cfg.CAM_NIGHT)
                time.sleep(0.5)
                cfg.NIGHT_VISION = True
                print("Bascule vision nocturne")

    now_t = time.time()

    # Detection de personnes - rotation gauche > droite > arriere, cadence DETECT_PERIOD
    # Une camera absente ou figee (image trop ancienne) est sautee, sans bloquer la rotation
    detector.poll()
    if not cfg.NIGHT_VISION and now_t - detect_last > cfg.DETECT_PERIOD:
        cam = {'L': cam_left, 'R': cam_right, 'B': cam_back}[detect_side]
        suivant = {'L': 'R', 'R': 'B', 'B': 'L'}[detect_side]
        if (cam is None or cam.frame is None
                or now_t - (cam.timestamp or 0) > cfg.CAM_FRAICHEUR):
            detect_side = suivant
        elif detector.submit(cam.frame, detect_side):
            detect_last = now_t
            detect_side = suivant

    nL, nR, nB = detector.compte('L'), detector.compte('R'), detector.compte('B')
    if nL > 0:
        alert_l_time = now_t
    if nR > 0:
        alert_r_time = now_t
    if nB > 0:
        alert_b_time = now_t

    # Dimensions zone utile (marges de securite Xreal)
    HUD_W = int(cfg.ECRAN_W * (1 - cfg.MARGE_G - cfg.MARGE_D))
    HUD_H = int(cfg.ECRAN_H * (1 - 2 * cfg.MARGE_Y))

    # Fond : video nocturne, ou noir pour transparence
    if cfg.NIGHT_VISION and cam_night is not None and cam_night.frame is not None:
        hud = cv2.resize(cam_night.frame, (HUD_W, HUD_H))
        if len(hud.shape) == 2:
            hud = cv2.cvtColor(hud, cv2.COLOR_GRAY2BGR)
        hud = cv2.flip(hud, -1)
    else:
        hud = np.zeros((HUD_H, HUD_W, 3), dtype=np.uint8)

    # Zone A - Donnees systeme (tous modes)
    cams_hs = [nom for nom, cam in (("G", cam_left), ("D", cam_right), ("AR", cam_back))
               if cam is not None and (cam.frame is None
                                       or now_t - (cam.timestamp or 0) > cfg.CAM_FRAICHEUR)]
    hud = draw.draw_zone_c(hud, fps, "", jetson_temp, cpu_percent, lat_display, gps, radar,
                               casque, cams_hs)

    if cfg.actif("boussole") or cfg.actif("altimetre") or cfg.actif("horizon"):
        # Zone B - Boussole, altimetre, horizon
        hud = draw.draw_zone_b(hud, casque.roll, casque.pitch, casque.yaw, bme.pressure)

    # Zone C - Navigation GPS et minimap
    if cfg.actif("minimap"):
        ms = cfg.MINIMAP_SIZE.get(cfg.MODE, 260)
        if (minimap_cache is None or minimap_cache.shape[0] != ms
                or abs(gps.lat - minimap_last_lat) > 0.0001
                or abs(gps.lon - minimap_last_lon) > 0.0001):
            minimap_cache = draw.get_minimap(gps.lat, gps.lon, zoom=14, size=ms)
            minimap_last_lat = gps.lat
            minimap_last_lon = gps.lon
        hud[60:60+ms, HUD_W-ms:HUD_W] = minimap_cache

    # Zone Centre - reticule et POI
    hud = draw.draw_zone_centre(hud)
    if cfg.actif("poi"):
        hud = draw.draw_poi(hud, casque.yaw, casque.pitch)

    # Zone D/E - Distance radar et vignettes des personnes detectees
    if cfg.actif("radar"):
        hud = draw.draw_zone_e(hud, radar.targets)
    if cfg.actif("vignettes"):
        hud = draw.draw_vignettes(hud, detector)

    # Cadran vue de dessus
    if cfg.actif("cadran"):
        hud = draw.draw_sentinelle(hud, radar.targets,
                                   now_t - alert_l_time < cfg.ALERT_DURATION,
                                   now_t - alert_r_time < cfg.ALERT_DURATION,
                                   detector,
                                   now_t - alert_b_time < cfg.ALERT_DURATION)

    # Zone G - OCR
    if cfg.actif("ocr"):
        if count % cfg.OCR_EVERY == 0 and cam_left and cam_left.frame is not None:
            ocr.submit(cv2.flip(cam_left.frame.copy(), -1))
        ocr.poll()
        hud = draw.draw_zone_g(hud, ocr.text)

    # Zone H - Donnees environnement
    if cfg.actif("environnement"):
        hud = draw.draw_zone_h(hud, bme.temperature, bme.humidity, bme.gas, bme.pressure,
                               bme.chauffe_restante)

    # Zone I - Alertes critiques (tous modes)
    if bme.gaz_pret and 0 < bme.gas < cfg.SEUIL_RES_GAS:
        hud = draw.draw_zone_i(hud, "!!! ALERTE GAZ !!!")
    if bme.temperature > cfg.SEUIL_TEMP_EXT:
        hud = draw.draw_zone_i(hud, f"!!! TEMP EXT {bme.temperature:.1f}C !!!", (0, 165, 255))
    if jetson_temp > cfg.SEUIL_TEMP_JETSON:
        hud = draw.draw_zone_i(hud, f"!!! SURCHAUFFE JETSON {jetson_temp:.0f}C !!!", (0, 0, 255))

    if cfg.DEBUG:
        hud = draw.draw_timestamp_debug(hud)

    count += 1
    fps = count / (time.time() - t0)

    # Composition finale : HUD centre sur fond noir plein ecran
    ecran = np.zeros((cfg.ECRAN_H, cfg.ECRAN_W, 3), dtype=np.uint8)
    ox = int(cfg.ECRAN_W * cfg.MARGE_G)
    oy = (cfg.ECRAN_H - HUD_H) // 2
    ecran[oy:oy+HUD_H, ox:ox+HUD_W] = hud

    # Bandes d'alerte laterales dans les marges, symetriques autour du HUD
    if cfg.actif("bandes"):
        ecran = draw.draw_alert_bars(ecran, ox, oy, HUD_W, HUD_H,
                                     now_t - alert_l_time < cfg.ALERT_DURATION,
                                     now_t - alert_r_time < cfg.ALERT_DURATION,
                                     now_t - alert_b_time < cfg.ALERT_DURATION)

    cv2.imshow("IPES HUD V1", ecran)

    # ------------------------------------------------------------------------- Entrees clavier
    key = cv2.waitKey(1) & 0xFF
    kb_key = kb.get()
    if kb_key:
        key = ord(kb_key)

    # Rotatif du brassard : selecteur de mode absolu, il prime sur le clavier
    rot = casque.brassard.get("rot")
    if rot is not None and rot != rot_precedent:
        rot_precedent = rot
        nouveau = cfg.ROT_MODES.get(rot)
        if nouveau and nouveau != cfg.MODE:
            cfg.MODE = nouveau
            cfg.appliquer_mode(nouveau)
            minimap_cache = None
            print("Mode:", cfg.MODE, "(rotatif %d)" % rot)
        elif nouveau is None:
            print("Rotatif position %d : non attribuee" % rot)

    # Boutons du brassard : l'evenement naît au relachement, avec sa duree
    for bouton, duree in casque.evenements():
        t = casque.duree_type(duree)
        print("Brassard : %s %s (%.2f s)" % (bouton, t, duree))

        if t == "tres_long" and bouton != cfg.BOUTON_EXTINCTION:
            t = "long"                             # un appui trop long ailleurs reste un appui long

        if t == "tres_long":
            cfg.MODE = "OFF"
            cfg.appliquer_mode("OFF")
            cfg.poi = None
            minimap_cache = None
            rot_precedent = None
            print("EXTINCTION TOTALE")
            continue

        touches = cfg.TOUCHES.get(cfg.MODE, ("", "", ""))
        if bouton in ("t1", "t2", "t3"):
            action = touches[int(bouton[1]) - 1]
            if not action:
                print("  touche sans fonction dans ce mode")
            elif action == "CAPTURE":
                capturer(ecran, casque, gps, bme)
            elif action == "POI":
                if t == "long":
                    cfg.poi = None
                    print("  POI efface")
                elif not casque.imu_ok:
                    print("  POI refuse : pas d'orientation du casque")
                else:
                    cfg.poi = {"yaw": casque.yaw, "pitch": casque.pitch, "t": now_t}
                    print("  POI verrouille yaw=%.1f pitch=%.1f" % (casque.yaw, casque.pitch))
            elif action == "CAMERA":
                key = ord('n')                     # reutilise la bascule nocturne existante
            elif action == "MARQUEUR":
                marqueurs.append({"lat": gps.lat, "lon": gps.lon, "t": now_t})
                print("  Marqueur %d pose (%.5f, %.5f)" % (len(marqueurs), gps.lat, gps.lon))

        elif bouton == "coude":
            if t == "court":
                visiere = (visiere + 1) % cfg.VISIERE_NIVEAUX
                casque.commande("visiere", visiere, attendre=False)
                print("  Visiere niveau", visiere)
            else:
                casque.commande("visiere_ecran", attendre=False)
                print("  Ecran Xreal ON/OFF")

        elif bouton == "rot":
            print("  Action principale du mode (a definir)")

        elif bouton == "enc":
            print("  Validation (a definir)")

    if key == ord('q'):
        break

    elif key == ord('n'):
        # Bascule nocturne : les cameras ne peuvent pas cohabiter sur le hub USB
        if not cfg.NIGHT_VISION:
            cam_left.stop()
            cam_right.stop()
            time.sleep(0.5)
            cam_night = CameraThread(cfg.CAM_NIGHT)
            time.sleep(0.5)
            cfg.NIGHT_VISION = True
            print("Vision nocturne ON")
        else:
            cam_night.stop()
            cam_night = None
            time.sleep(0.5)
            cam_left = CameraThread(cfg.CAM_LEFT, period=cfg.CAM_PERIOD)
            cam_right = CameraThread(cfg.CAM_RIGHT, period=cfg.CAM_PERIOD)
            time.sleep(0.5)
            cfg.NIGHT_VISION = False
            print("Vision nocturne OFF")

    elif key in (ord('1'), ord('2'), ord('3'), ord('4'), ord('5')):
        cfg.MODE = cfg.MODES[key - ord('1')]
        cfg.appliquer_mode(cfg.MODE)
        minimap_cache = None
        print("Mode:", cfg.MODE)

    elif key == ord('m'):
        cfg.MODE = cfg.MODES[(cfg.MODES.index(cfg.MODE) + 1) % len(cfg.MODES)]
        cfg.appliquer_mode(cfg.MODE)
        minimap_cache = None
        print("Mode:", cfg.MODE)

    elif key == ord('v'):
        if not casque.imu_ok:
            print("POI refuse : pas d'orientation du casque")
        else:
            cfg.poi = {"yaw": casque.yaw, "pitch": casque.pitch, "t": time.time()}
            print("POI verrouille yaw=%.1f pitch=%.1f" % (casque.yaw, casque.pitch))

    elif key == ord('c'):
        cfg.poi = None
        print("POI efface")

    elif 32 <= key < 127 and chr(key) in cfg.TOUCHES_COUCHES:
        basculer(cfg.TOUCHES_COUCHES[chr(key)])

    elif key == ord('i'):
        print("Mode %s | actives   : %s"
              % (cfg.MODE, " ".join(sorted(cfg.couches)) or "(aucune)"))
        print("            inactives : %s"
              % (" ".join(c for c in cfg.COUCHES if c not in cfg.couches) or "(aucune)"))

    elif key == ord('s'):
        cv2.imwrite(f'/tmp/ipes_capture_{int(time.time())}.png', ecran)
        print("Capture sauvegardee")

#----------------------------------------------------------------------------- Arret propre
print(f"\nFPS pipeline complet : {fps:.1f}")
if cam_left:
    cam_left.stop()
if cam_right:
    cam_right.stop()
if cam_night:
    cam_night.stop()
if cam_back:
    cam_back.stop()
detector.stop()
casque.stop()
if xdisp:
    xdisp.screen().root.xfixes_show_cursor()
    xdisp.close()
cv2.destroyAllWindows()
