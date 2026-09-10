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
#   1-4 mode direct     m  mode suivant
#   v  verrouiller POI  c  effacer POI
import time

import cv2
import numpy as np
import psutil

import hud_config as cfg
from sensors import (IMUThread, BMEThread, GPSThread, RadarThread,
                     CameraThread, KeyboardThread)
from ocr_process import OCRProcess
from person_detect import PersonDetector
import hud_draw as draw


#----------------------------------------------------------------------------- Instanciations
cam_left = CameraThread(cfg.CAM_LEFT, period=1.0)
time.sleep(1)
cam_right = CameraThread(cfg.CAM_RIGHT, period=1.0)
time.sleep(1)
cam_night = None

imu = IMUThread()
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
lat_display = 0

alert_l_time = 0
alert_r_time = 0

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

    # Detection de personnes - alternance gauche/droite, 1 Hz
    detector.poll()
    if not cfg.NIGHT_VISION and now_t - detect_last > 1.0:
        cam = cam_left if detect_side == 'L' else cam_right
        if cam is not None and cam.frame is not None:
            if detector.submit(cam.frame, detect_side):
                detect_last = now_t
                detect_side = "R" if detect_side == "L" else "L"

    nL, nR = detector.compte('L'), detector.compte('R')
    if count % 60 == 0 and (nL or nR):
        print("PERSONNES  G:%d  D:%d  (%.0f ms)" % (nL, nR, detector.latence))
    if nL > 0:
        alert_l_time = now_t
    if nR > 0:
        alert_r_time = now_t

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
    hud = draw.draw_zone_c(hud, fps, "", jetson_temp, cpu_percent, lat_display)

    if cfg.MODE != "OFF":
        # Zone B - Boussole et altimetre
        hud = draw.draw_zone_b(hud, imu.roll, imu.pitch, imu.yaw, bme.pressure)

        # Zone C - Navigation GPS et minimap
        if cfg.MODE in cfg.MINIMAP_SIZE:
            ms = cfg.MINIMAP_SIZE[cfg.MODE]
            if (minimap_cache is None or minimap_cache.shape[0] != ms
                    or abs(gps.lat - minimap_last_lat) > 0.0001
                    or abs(gps.lon - minimap_last_lon) > 0.0001):
                minimap_cache = draw.get_minimap(gps.lat, gps.lon, zoom=14, size=ms)
                minimap_last_lat = gps.lat
                minimap_last_lon = gps.lon
            hud[60:60+ms, HUD_W-ms:HUD_W] = minimap_cache

        # Zone Centre - reticule et POI
        hud = draw.draw_zone_centre(hud)
        hud = draw.draw_poi(hud, imu.yaw, imu.pitch)

        # Zone D/E - Fleches d'alerte et vignettes
        hud = draw.draw_zone_d(hud, now_t - alert_l_time < cfg.ALERT_DURATION)
        hud = draw.draw_zone_e(hud, now_t - alert_r_time < cfg.ALERT_DURATION, radar.targets)
        hud = draw.draw_vignettes(hud, detector)

        if cfg.MODE != "MINIMAL":
            # Zone G - OCR
            if cfg.ACTIVATE_OCR and count % 150 == 0:
                if cam_left and cam_left.frame is not None:
                    ocr.submit(cv2.flip(cam_left.frame.copy(), -1))
            ocr.poll()
            if cfg.SHOW_OCR:
                hud = draw.draw_zone_g(hud, ocr.text)

            # Zone H - Donnees environnement
            hud = draw.draw_zone_h(hud, bme.temperature, bme.humidity, bme.gas, bme.pressure)

    # Zone I - Alertes critiques (tous modes)
    if 0 < bme.gas < cfg.SEUIL_RES_GAS:
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

    # Barres laterales d'alerte dans les marges (hors zone utile)
    if cfg.MODE != "OFF":
        if now_t - alert_l_time < cfg.ALERT_DURATION:
            cv2.rectangle(ecran, (0, 0), (12, cfg.ECRAN_H), (0, 165, 255), -1)
        if now_t - alert_r_time < cfg.ALERT_DURATION:
            cv2.rectangle(ecran, (cfg.ECRAN_W - 12, 0),
                          (cfg.ECRAN_W, cfg.ECRAN_H), (0, 165, 255), -1)

    cv2.imshow("IPES HUD V1", ecran)

    # ------------------------------------------------------------------------- Entrees clavier
    key = cv2.waitKey(1) & 0xFF
    kb_key = kb.get()
    if kb_key:
        key = ord(kb_key)

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
            cam_left = CameraThread(cfg.CAM_LEFT, period=1.0)
            cam_right = CameraThread(cfg.CAM_RIGHT, period=1.0)
            time.sleep(0.5)
            cfg.NIGHT_VISION = False
            print("Vision nocturne OFF")

    elif key in (ord('1'), ord('2'), ord('3'), ord('4')):
        cfg.MODE = cfg.MODES[key - ord('1')]
        minimap_cache = None
        print("Mode:", cfg.MODE)

    elif key == ord('m'):
        cfg.MODE = cfg.MODES[(cfg.MODES.index(cfg.MODE) + 1) % len(cfg.MODES)]
        minimap_cache = None
        print("Mode:", cfg.MODE)

    elif key == ord('v'):
        cfg.poi = {"yaw": imu.yaw, "pitch": imu.pitch, "t": time.time()}
        print("POI verrouille yaw=%.1f pitch=%.1f" % (imu.yaw, imu.pitch))

    elif key == ord('c'):
        cfg.poi = None
        print("POI efface")

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
detector.stop()
cv2.destroyAllWindows()
