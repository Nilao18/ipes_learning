import cv2
import numpy as np
import threading
import time
from datetime import datetime
import math
import os
from PIL import Image
from adafruit_extended_bus import ExtendedI2C as I2C # Import adafruit après le reset
from adafruit_bno08x.i2c import BNO08X_I2C
from adafruit_bno08x import BNO_REPORT_ROTATION_VECTOR
import adafruit_bme680
import psutil
import subprocess
import serial
import pynmea2
import multiprocessing as mp
import struct
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

# Zone A - Navigation GPS + minimap
# Zone B - Boussole + Altimètre
# Zone C - Infos système (heure/date/FPS/latence/écran droit ou gauche)
# Zone D - Alerte mouvement coté gauche
# Zone E - Alerte mouvement coté droit
# Zone F - Biodata (Fréquence cardiaque/SPO2/Temperature corporelle)
# Zone G - Transcription et traduction en temps réel (texte + voix)
# Zone H - Infos environnement (Température/humidité/présence gaz)
# Zone I - Bandeau d'alerte central (temporaire)

# Variables pour affichage éléments
DEBUG = False #True pour afficher FPS/LAT (Zone C) + PITCH/YAW/ROLL (Zone B) + Ecran droit ou gauche (Zone C)
SHOW_RETICULE = False # True pour afficher le réticule central (Zone CENTRE)
SHOW_HORIZON = False # True pour afficher l'horizon artificiel (Zone CENTRE)
SHOW_COMPASS = True # True pour afficher la boussole (Zone B)
SHOW_ALTITUDE = True # True pour afficher l'altitude (Zone B
SHOW_GAS_RES = False # True pour afficher la resistance de la mesure de gaz
ACTIVATE_OCR = True  # True pour activer le traitement OCR (Zone G)
SHOW_OCR = True      # True pour afficher le traitement OCR (Zone G)

# Chemins 
TILES_DIR = "/home/quentin/ipes/maps/tours" # Chemin vers répertoir minimap

CAM_LEFT  = "/dev/v4l/by-path/platform-3610000.usb-usb-0:1.1:1.0-video-index0"
CAM_RIGHT = "/dev/v4l/by-path/platform-3610000.usb-usb-0:1.4:1.0-video-index0"
CAM_NIGHT = "/dev/v4l/by-path/platform-3610000.usb-usb-0:1.3:1.0-video-index0"

NIGHT_VISION = False  # True = caméra nocturne active
NIGHT_VISION_AUTO_SWITCH = False  # True = bascule auto après délai
NIGHT_VISION_DELAY = 10  # secondes avant bascule auto

#------------------------------------------------------------------------------------
# Thread IMU (BNO085)- Inertial Mesurement Unit / Centrale Inertielle : Pitch, Yaw, Roll
#------------------------------------------------------------------------------------
class IMUThread:
    def __init__(self):
        print("Init IMU...")
        i2c = I2C(1)
        print("I2C OK")
        self.bno = BNO08X_I2C(i2c, address=0x4A)
        print("BNO08X OK")
        self.bno.soft_reset()
        time.sleep(1)
        self.bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)
        print("Feature OK")
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        print("Pitch/Yaw/Roll OK")
        self.running = True
        self.thread = threading.Thread(target=self.update)
        self.thread.daemon = True
        self.thread.start()
        print("Thread Start OK")

    def update(self):
        while self.running:
            quat = self.bno.quaternion
            if quat:
                qi, qj, qk, real = quat
                self.roll  = math.degrees(math.atan2(2*(real*qi + qj*qk), 1 - 2*(qi*qi + qj*qj)))
                self.pitch = math.degrees(math.asin(max(-1, min(1, 2*(real*qj - qk*qi)))))
                self.yaw   = math.degrees(math.atan2(2*(real*qk + qi*qj), 1 - 2*(qj*qj + qk*qk)))
            time.sleep(0.02)  # 50Hz

    def stop(self):
        self.running = False

#-----------------------------------------------------------------------------------
#Thread BME (BME688) - Capteur de température, humidité et gaz
#-----------------------------------------------------------------------------------
class BMEThread:
    def __init__(self):
        print("Init BME688...")
        i2c = I2C(7)
        self.bme = adafruit_bme680.Adafruit_BME680_I2C(i2c, address=0x77)
        self.bme.sea_level_pressure = 1013.25
        self.temperature = 0.0
        self.humidity = 0.0
        self.pressure = 0.0
        self.gas = 0
        self.running = True
        self.thread = threading.Thread(target=self.update)
        self.thread.daemon = True
        self.thread.start()
        print("BME688 OK")

    def update(self):
        while self.running:
            try:
                self.temperature = self.bme.temperature
                self.humidity = self.bme.humidity
                self.pressure = self.bme.pressure
                self.gas = self.bme.gas
            except Exception as e:
                print(f"BME erreur: {e}")
            time.sleep(2)

    def stop(self):
        self.running = False

#-----------------------------------------------------------------------------------
#Thread GPS - Position en temps réel
#-----------------------------------------------------------------------------------
class GPSThread:
    def __init__(self):
        print("Init GPS...")
        self.ser = serial.Serial('/dev/ttyTHS1', 9600, timeout=2)
        self.lat = 47.3941  # position par défaut Tours
        self.lon = 0.6848
        self.alt = 0.0
        self.speed = 0.0
        self.satellites = 0
        self.fix = False
        self.running = True
        self.thread = threading.Thread(target=self.update)
        self.thread.daemon = True
        self.thread.start()
        print("GPS OK")

    def update(self):
        while self.running:
            try:
                line = self.ser.readline().decode('ascii', errors='replace').strip()
                if line.startswith('$GNGGA'):
                    msg = pynmea2.parse(line)
                    self.satellites = int(msg.num_sats)
                    self.fix = int(msg.gps_qual) > 0
                    if self.fix:
                        self.alt = float(msg.altitude) if msg.altitude else 0.0
                elif line.startswith('$GNRMC'):
                    msg = pynmea2.parse(line)
                    if msg.status == 'A':
                        self.lat = msg.latitude
                        self.lon = msg.longitude
                        self.speed = float(msg.spd_over_grnd) * 1.852  # kts → km/h
            except:
                pass

    def stop(self):
        self.running = False
        self.ser.close()

#-----------------------------------------------------------------------------------
#Thread HLK-LD2450 - Radar 24ghz
#-----------------------------------------------------------------------------------
class RadarThread:
    def __init__(self):
        print("Init Radar...")
        self.ser = serial.Serial('/dev/ttyUSB0', 256000, timeout=1)
        self.targets = []
        self._dist_history = []
        self.smooth_dist = 0.0
        self.running = True
        self.thread = threading.Thread(target=self.update)
        self.thread.daemon = True
        self.thread.start()
        print("Radar OK")

    def _decode_coord(self, raw):
        sign = -1 if (raw & 0x8000) else 1
        return sign * (raw & 0x7FFF) / 1000.0

    def update(self):
        buf = bytearray()
        while self.running:
            try:
                buf += self.ser.read(64)
                start = -1
                for i in range(len(buf) - 1):
                    if buf[i] == 0xAA and buf[i+1] == 0xFF:
                        start = i
                        break
                if start == -1:
                    if len(buf) > 512:
                        buf = bytearray()
                    continue
                end = -1
                for i in range(start, len(buf) - 1):
                    if buf[i] == 0x55 and buf[i+1] == 0xCC:
                        end = i + 2
                        break
                if end == -1:
                    continue
                frame = buf[start:end]
                buf = buf[end:]
                if len(frame) < 30:
                    continue
                targets = []
                for t in range(3):
                    offset = 4 + t * 8
                    if offset + 8 > len(frame):
                        break
                    x = self._decode_coord(struct.unpack_from('<H', frame, offset)[0])
                    y = self._decode_coord(struct.unpack_from('<H', frame, offset+2)[0])
                    spd = self._decode_coord(struct.unpack_from('<H', frame, offset+4)[0])
                    if x != 0 or y != 0:
                        dist = (x**2 + y**2) ** 0.5
                        if 0.1 < dist < 6.0:  # ignorer < 10cm et > 6m
                            targets.append({'x': x, 'y': y, 'speed': spd})
                self.targets = targets
                if targets:
                    closest = min(targets, key=lambda t: t['x']**2 + t['y']**2)
                    dist = (closest['x']**2 + closest['y']**2) ** 0.5
                    self._dist_history.append(dist)
                    if len(self._dist_history) > 10:
                        self._dist_history.pop(0)
                    self.smooth_dist = sum(self._dist_history) / len(self._dist_history)
            except Exception as e:
                print(f"Radar erreur: {e}")
                pass

    def stop(self):
        self.running = False
        self.ser.close()

#-----------------------------------------------------------------------------------
#Thread OCR - Transcription texte et voix / traduction temps réel
#-----------------------------------------------------------------------------------
class OCRProcess:
    def __init__(self):
        print("Init OCR...")
        self.input_queue = mp.Queue(maxsize=1)
        self.output_queue = mp.Queue(maxsize=1)
        self.process = mp.Process(
            target=ocr_worker,
            args=(self.input_queue, self.output_queue),
            daemon=True
        )
        self.process.start()
        self.text = ""
        self.busy = False
        print("OCR OK")

    def submit(self, frame):
        if not self.busy and not self.input_queue.full():
            self.input_queue.put(frame.copy())
            self.busy = True

    def poll(self):
        if self.busy and not self.output_queue.empty():
            self.text = self.output_queue.get()
            self.busy = False

    def stop(self):
        self.input_queue.put(None)
        self.process.join(timeout=3)
#-----------------------------------------------------------------------------------
#Thread Camera - Capture via camera
#-----------------------------------------------------------------------------------
class CameraThread:
    def __init__(self, device):
        self.cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.frame = None
        self.timestamp = None
        self.running = True
        self.thread = threading.Thread(target=self.update)
        self.thread.daemon = True
        self.thread.start()

    def update(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                self.frame = frame
                self.timestamp = time.time()

    def stop(self):
        self.running = False
        self.cap.release()

# -------------------------------------------------------------------------------Detection de texte
def ocr_worker(input_queue, output_queue):
    """Processus séparé pour l'OCR - contourne le GIL"""
    from onnxtr.models import ocr_predictor
    from onnxtr.io import DocumentFile
    import cv2
    model = ocr_predictor(
        det_arch="db_mobilenet_v3_large",
        reco_arch="crnn_mobilenet_v3_small"
    )
    while True:
        frame = input_queue.get()
        if frame is None:
            break
        try:
            tmp = '/tmp/ipes_ocr_frame.png'
            cv2.imwrite(tmp, frame)
            doc = DocumentFile.from_images(tmp)
            result = model(doc)
            text = result.render().strip()
            lines = [l for l in text.split('\n') if len(l.strip()) > 2]
            output_queue.put(' | '.join(lines[-2:]) if lines else "")
        except Exception as e:
            output_queue.put("")


# -------------------------------------------------------------------------------Detection de mouvements latérale
def detect_motion_zone(prev_gray, gray, seuil=10):
    small_prev = cv2.resize(prev_gray, (160, 90))
    small_gray = cv2.resize(gray, (160, 90))
    diff = cv2.absdiff(small_prev, small_gray)
    _, thresh = cv2.threshold(diff, seuil, 255, cv2.THRESH_BINARY)
    w = thresh.shape[1]
    motion_left  = np.sum(thresh[:, :w//2]) / 255
    motion_right = np.sum(thresh[:, w//2:]) / 255
    return motion_left, motion_right

#------------------------------------------------------------------------------ Affichage horizon artificiel
def draw_horizon(frame, roll, pitch):
    h, w = frame.shape[:2]
    cx, cy = w // 2, h // 2
    color = (0, 255, 0)

    # Décalage vertical selon le pitch (1 pixel par degré)
    pitch_offset = int(pitch * 4)

    # Longueur de la ligne d'horizon
    length = w // 2

    # Calcul des extrémités selon le roll
    angle_rad = math.radians(roll)
    dx = int(length * math.cos(angle_rad))
    dy = int(length * math.sin(angle_rad))

    # Points de la ligne d'horizon
    x1 = cx - dx
    y1 = cy + pitch_offset + dy
    x2 = cx + dx
    y2 = cy + pitch_offset - dy

    cv2.line(frame, (x1, y1), (x2, y2), color, 3)

    # Marqueur centre fixe (repère casque)
    cv2.line(frame, (cx - 60, cy), (cx - 20, cy), (255, 255, 255), 3)
    cv2.line(frame, (cx + 20, cy), (cx + 60, cy), (255, 255, 255), 3)
    cv2.circle(frame, (cx, cy), 5, (255, 255, 255), -1)

    return frame

#----------------------------------------------------------------------Affichage boussole
def draw_compass(frame, yaw):
    h, w = frame.shape[:2]
    cx = w // 2
    compass_y = 40
    compass_w = w // 2 # moitié de la largeur au lieu de w - 100
    deg_per_px = compass_w / 60.0  # 60° visibles au total

    color_small = (0, 200, 0)
    color_large = (255, 255, 255)
    color_cardinal = (0, 200, 255)

    cardinals = {0: 'N', 45: 'NE', 90: 'E', 135: 'SE',
                 180: 'S', 225: 'SO', 270: 'O', 315: 'NO'}

    # Ligne de base
    cv2.line(frame, (cx - compass_w//2, compass_y),
             (cx + compass_w//2, compass_y), color_small, 2)

    # Dessiner 360° de graduations centrées sur yaw
    for deg in range(0, 360):
        # Distance angulaire par rapport au cap actuel
        diff = (deg - yaw + 180) % 360 - 180
        if abs(diff) > 30:  # 30° de chaque côté = 60° visibles
            continue

        px = cx + int(diff * deg_per_px)

        if deg % 45 == 0:
            # Grand trait + cardinal
            cv2.line(frame, (px, compass_y - 5), (px, compass_y + 25), color_cardinal, 3)
            label = cardinals.get(deg, '')
            cv2.putText(frame, label, (px - 12, compass_y + 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_cardinal, 3)
        elif deg % 10 == 0:
            # Trait moyen + chiffre
            cv2.line(frame, (px, compass_y - 3), (px, compass_y + 18), color_large, 2)
            cv2.putText(frame, str(deg), (px - 10, compass_y + 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_large, 2)
        elif deg % 5 == 0:
            # Trait moyen sans chiffre
            cv2.line(frame, (px, compass_y), (px, compass_y + 12), color_small, 2)
        else:
            # Petit trait
            cv2.line(frame, (px, compass_y), (px, compass_y + 6), color_small, 2)

    # Marqueur cap fixe (triangle)
    pts = np.array([[cx, compass_y - 4], [cx - 12, compass_y - 16], [cx + 12, compass_y - 16]])
    cv2.fillPoly(frame, [pts], color_large)

    return frame

#---------------------------------------------------------------------------- Chargement de la minimap
def get_minimap(lat, lon, zoom=14, size=250):
    x_tile, y_tile = deg2tile(lat, lon, zoom)
    tile_size = 256
    
    # Calcul position exacte en pixels dans la tuile
    n = 2 ** zoom
    lat_r = math.radians(lat)
    px_exact = (lon + 180) / 360 * n * tile_size
    py_exact = (1 - math.log(math.tan(lat_r) + 1/math.cos(lat_r)) / math.pi) / 2 * n * tile_size
    
    # Décalage par rapport au coin de la tuile centrale
    px_in_tile = px_exact - x_tile * tile_size
    py_in_tile = py_exact - y_tile * tile_size
    
    canvas = np.zeros((size, size, 3), dtype=np.uint8)
    
    for dx in range(-1, 2):
        for dy in range(-1, 2):
            tx = x_tile + dx
            ty = y_tile + dy
            path = os.path.join(TILES_DIR, str(zoom), str(tx), f"{ty}.png")
            if not os.path.exists(path):
                continue
            img = np.array(Image.open(path).convert('RGB'))
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            
            # Position de la tuile sur le canvas
            # Centre du canvas = position exacte GPS
            cx = size//2 + dx * tile_size - int(px_in_tile)
            cy = size//2 + dy * tile_size - int(py_in_tile)
            
            x1 = max(0, cx)
            y1 = max(0, cy)
            x2 = min(size, cx + tile_size)
            y2 = min(size, cy + tile_size)
            
            sx1 = max(0, -cx)
            sy1 = max(0, -cy)
            
            if x2 > x1 and y2 > y1:
                canvas[y1:y2, x1:x2] = img[sy1:sy1+(y2-y1), sx1:sx1+(x2-x1)]
    
    # Marqueur position — maintenant vraiment au centre
    cv2.circle(canvas, (size//2, size//2), 6, (0, 0, 255), -1)
    cv2.circle(canvas, (size//2, size//2), 8, (255, 255, 255), 2)
    
    return canvas
#----------------------------------- Conversion de le position en coordonnées GPS vers position sur tuille minimap
def deg2tile(lat, lon, zoom):
    lat_r = math.radians(lat)
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(lat_r) + 1/math.cos(lat_r)) / math.pi) / 2 * n)
    return x, y

# --------------------------------------------------------------------------------Affichage de la Zone A
def draw_zone_a(frame, lat, lon, zoom=14):
    h, w = frame.shape[:2]
    
    minimap = get_minimap(lat, lon, zoom=zoom, size=250)
    
    # Bordure zone A
    cv2.rectangle(minimap, (0, 0), (199, 199), (0, 150, 0), 1)
    cv2.putText(minimap, "NAV", (5, 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 150, 0), 1)
    
    # Coller en haut gauche
    frame[0:250, 0:250] = minimap
    
    return frame

# --------------------------------------------------------------------------------Affichage de la Zone B
def draw_zone_b(frame, roll, pitch, yaw, pressure=1013.25):
    h, w = frame.shape[:2]
    cx = w // 2
    compass_w = w // 2

    # Fond semi-transparent derrière la zone boussole + altimètres
    overlay = frame.copy()

    # Fond derrière boussole
    if SHOW_COMPASS:
        cv2.rectangle(overlay, 
                      (cx - compass_w//2 - 5, 0), 
                      (cx + compass_w//2 + 5, 95), 
                      (0, 0, 0), -1)

    # Fond derrière curseur gauche (pieds)
    if SHOW_ALTITUDE:
        cv2.rectangle(overlay,
                      (cx - compass_w//2 - 110, 0),
                      (cx - compass_w//2, 240),
                      (0, 0, 0), -1)
        # Fond derrière curseur droit (mètres)
        cv2.rectangle(overlay,
                      (cx + compass_w//2, 0),
                      (cx + compass_w//2 + 110, 240),
                      (0, 0, 0), -1)

    cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

    # Horizon artificiel
    if SHOW_HORIZON:
        frame = draw_horizon(frame, roll, pitch)
    
    # Boussole
    COMPASS_OFFSET = -45
    if SHOW_COMPASS:
        frame = draw_compass(frame, (-yaw + COMPASS_OFFSET) % 360)
    
    # Curseurs altitude
    alt_m = 44330 * (1 - (pressure / 1013.25) ** 0.1903)
    alt_ft = alt_m * 3.28084

    color_large = (255, 255, 255)
    color_small = (0, 200, 0)
    color_dim = (0, 150, 0)
    
    compass_left  = cx - compass_w//2 - 10  # juste à gauche de la boussole
    compass_right = cx + compass_w//2 + 10  # juste à droite

    if SHOW_ALTITUDE:
        # Curseur gauche = pieds
        cv2.putText(frame, "FT", (compass_left - 60, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 2)
        #cv2.putText(frame, f"{alt_ft:.0f}", (compass_left - 30, 120 + 5),
        #       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_large, 2)

        # Curseur droit = mètres
        cv2.putText(frame, "M", (compass_right + 50, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 2)
        #cv2.putText(frame, f"{alt_m:.0f}", (compass_right, 120 + 5),
        #        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_large, 2)
    
        # Graduation verticale altitude — gauche (pieds)
        grad_h = 200  # hauteur totale de la graduation
        grad_x_l = compass_left - 5
        grad_y_center = 120  # centre vertical
        cv2.line(frame, (grad_x_l, grad_y_center - grad_h//2),
             (grad_x_l, grad_y_center + grad_h//2), color_dim, 2)

        for i in range(-5, 6):
            y = grad_y_center + i * 20

            if i == 0:
                # Valeur réelle — trait épais + texte blanc grand
                cv2.line(frame, (grad_x_l - 12, y), (grad_x_l, y), color_large, 3)
                txt_ft = f"{int(alt_ft)}"
                txt_ft_w = cv2.getTextSize(txt_ft, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0][0]
                cv2.putText(frame, txt_ft, (grad_x_l - 20 - txt_ft_w, y + 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_large, 2)
            elif i % 5 == 0:
                cv2.line(frame, (grad_x_l - 8, y), (grad_x_l, y), color_large, 3)
                cv2.putText(frame, f"{int(alt_ft - i*50)}", (grad_x_l - 50, y+5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 2)
            else:
                cv2.line(frame, (grad_x_l - 4, y), (grad_x_l, y), color_small, 2)

        # Graduation verticale altitude — droite (mètres)
        grad_x_r = compass_right + 5
        cv2.line(frame, (grad_x_r, grad_y_center - grad_h//2),
             (grad_x_r, grad_y_center + grad_h//2), color_dim, 2)

        for i in range(-5, 6):
            y = grad_y_center + i * 20
            if i == 0:
                # Valeur réelle — trait épais + texte blanc grand
                cv2.line(frame, (grad_x_r + 12, y), (grad_x_r, y), color_large, 3)
                cv2.putText(frame, f"{int(alt_ft)}", (grad_x_r + 20, y + 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_large, 2)
            elif i % 5 == 0:
                cv2.line(frame, (grad_x_r, y), (grad_x_r + 8, y), color_large, 3)
                cv2.putText(frame, f"{int(alt_m - i*15)}", (grad_x_r + 20, y+5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 2)
            else:
                cv2.line(frame, (grad_x_r, y), (grad_x_r + 4, y), color_small, 2)
    
    # R/P/Y — zone B haut gauche sous la boussole
    color_dim = (0, 150, 0)
    h, w = frame.shape[:2]
    cx = w // 2

    if DEBUG:
        cv2.putText(frame, f"R:{roll:6.1f}", (cx - 0, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 1)
        cv2.putText(frame, f"P:{pitch:6.1f}", (cx - 0, 120),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 1)
        cv2.putText(frame, f"Y:{yaw:6.1f}", (cx - 0, 140),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 1)    
    return frame

# --------------------------------------------------------------------------------Affichage de la Zone C
def draw_zone_c(frame, fps, side="", jetson_temp=0, cpu=0, lat=0):
    h, w = frame.shape[:2]
    # Zone C : haut droite 200x200px
    x = w - 195
    y = 10
    color_dim = (0, 150, 0)
    now = datetime.now()

    cv2.putText(frame, now.strftime("%H:%M:%S"), (x, y+20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color_dim, 2)
    cv2.putText(frame, now.strftime("%d/%m/%Y"), (x, y+50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color_dim, 2)

    # Température et charge Jetson
    temp_color = (0, 0, 255) if jetson_temp > 75 else color_dim
    cv2.putText(frame, f"CPU:{cpu:.0f}%", (x, y+80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color_dim, 2)
    cv2.putText(frame, f"T:{jetson_temp:.0f}°C", (x, y+110),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, temp_color, 2)

    # debug fps + latence
    if DEBUG:
        cv2.putText(frame, f"FPS:{fps:.1f}", (x, y+140),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_dim, 2)
        cv2.putText(frame, f"LAT:{lat:.0f}ms", (x, y+160),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_dim, 2)
        cv2.putText(frame, side, (x, y+180),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_dim, 2)

    return frame

# --------------------------------------------------------------------------------Affichage de la Zone D
def draw_zone_d(frame, alert_active):
    if not alert_active:
        return frame
    h, w = frame.shape[:2]
    # Zone D : centre gauche, 200px de large
    cy = h // 2
    # Flèche principale
    cv2.arrowedLine(frame, (190, cy), (30, cy), (0, 0, 255), 8, tipLength=0.4)
    # Texte alerte
    cv2.putText(frame, "MVT", (20, cy - 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    return frame

# --------------------------------------------------------------------------------Affichage de la Zone CENTRE
def draw_zone_centre(frame):
    if not SHOW_RETICULE:
        return frame
    h, w = frame.shape[:2]
    cx, cy = w//2, h//2
    color = (0, 255, 0)
    cv2.line(frame, (cx-20, cy), (cx+20, cy), color, 2)
    cv2.line(frame, (cx, cy-20), (cx, cy+20), color, 2)
    cv2.circle(frame, (cx, cy), 30, color, 2)
    return frame

# --------------------------------------------------------------------------------Affichage de la Zone E
def draw_zone_e(frame, alert_active, radar_targets=None):
    h, w = frame.shape[:2]
    cy = h // 2

    # Flèche alerte mouvement
    if alert_active:
        cv2.arrowedLine(frame, (w-190, cy), (w-30, cy), (0,0,255), 8, tipLength=0.4)
        cv2.putText(frame, "MVT", (w-70, cy-30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)

    # Cibles radar
    if radar_targets:
        cv2.putText(frame, "PRESENCE DETECTEE",
                    (w-220, cy + 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    return frame

# --------------------------------------------------------------------------------Affichage de la Zone G
def draw_zone_g(frame, text):
    if not text:
        return frame
    h, w = frame.shape[:2]
    
    # Zone G : bas centre 1040x200px
    x = 200
    y = h - 180
    zone_w = w - 400  # 1040px
    
    # Fond opaque derrière le texte uniquement
    cv2.rectangle(frame, (x, y - 10), (x + zone_w, h - 10), (0, 0, 0), -1)
    
    # Texte style sous-titres cinéma
    cv2.putText(frame, text[:80], (x + 10, y + 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    return frame

# --------------------------------------------------------------------------------Affichage de la Zone H
def draw_zone_h(frame, temperature, humidity, gas, pressure=0.0):
    h, w = frame.shape[:2]
    
    # Zone H : bas droite 200x200px
    x = w - 200
    y = h - 200
    
    color = (0, 255, 0)      # vert nominal
    color_dim = (0, 150, 0)
    
    # Fond opaque (règle LCD)
    cv2.rectangle(frame, (x, y), (w-1, h-1), (15, 20, 26), -1)
    cv2.rectangle(frame, (x, y), (w-1, h-1), color_dim, 1)
    
    # Label zone
    cv2.putText(frame, "ENV", (x+90, y+20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 2)
    
    # Température
    cv2.putText(frame, "TEMP :", (x+8, y+60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 2)
    cv2.putText(frame, f"{temperature:.1f}C", (x+65, y+60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    
    # Humidité
    cv2.putText(frame, "HUM :", (x+8, y+100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 2)
    cv2.putText(frame, f"{humidity:.0f}%", (x+65, y+100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    
    # Gaz VOC — indicateur qualitatif
    if gas > 50000:
        gaz_label = "AIR OK"
        gaz_color = (0, 255, 0)
    elif gas > 20000:
        gaz_label = "MOYEN"
        gaz_color = (0, 200, 255)
    else:
        gaz_label = "ALERTE"
        gaz_color = (0, 0, 255)

    cv2.putText(frame, "GAZ :", (x+8, y+140),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 2)
    cv2.putText(frame, gaz_label, (x+65, y+140),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, gaz_color, 2)

    if SHOW_GAS_RES:
        cv2.putText(frame, f"Gas res :{gas//1000}k ohm", (x+8, y+160),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 1)

    # Pression
    cv2.putText(frame, "PRES :", (x+8, y+180),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 2)
    cv2.putText(frame, f"{pressure:.1f}hPa", (x+65, y+180),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    
    return frame

# --------------------------------------------------------------------------------Affichage de la Zone I
def draw_zone_i(frame, message, color=(0, 0, 255)):
    h, w = frame.shape[:2]
    cy = h // 2
    
    # Fond semi-opaque pleine largeur
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, cy - 60), (w, cy + 60), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
    
    # Bordures
    cv2.line(frame, (0, cy - 60), (w, cy - 60), color, 2)
    cv2.line(frame, (0, cy + 60), (w, cy + 60), color, 2)
    
    # Texte centré
    text_size = cv2.getTextSize(message, cv2.FONT_HERSHEY_SIMPLEX, 1.2, 3)[0]
    tx = (w - text_size[0]) // 2
    cv2.putText(frame, message, (tx, cy + 15),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)
    
    return frame

#-----------------------------------------------------------------------------------Affichage time stamp
def draw_timestamp_debug(frame):
    h, w = frame.shape[:2]
    now = datetime.now()
    ts = f"{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}"
    cv2.putText(frame, ts, (w//2 - 250, h//2 + 200),
                cv2.FONT_HERSHEY_SIMPLEX, 2.5, (0, 255, 255), 5)
    return frame

#----------------------------------------------------------------------------- Instanciations
cam_left  = CameraThread(CAM_LEFT)
time.sleep(1)
cam_right = CameraThread(CAM_RIGHT)
time.sleep(1)
cam_night = None
time.sleep(1)
imu = IMUThread()
time.sleep(0.5)
bme = BMEThread()
time.sleep(0.5)
ocr = OCRProcess()
time.sleep(0.5)
gps = GPSThread()
time.sleep(1)
radar = RadarThread()
time.sleep(0.5)
#----------------------------------------------------------------------------- Initialisation
count = 0
fps = 0
lat_display = 0
lat_update = time.time()

prev_gray_l = None
prev_gray_r = None

alert_l_time = 0
alert_r_time = 0
ALERT_DURATION = 1.5
ZONE_SEUIL = 600
SEUIL_RES_GAS = 20000
SEUIL_TEMP_EXT = 35
SEUIL_TEMP_JETSON = 75

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
cv2.resizeWindow("IPES HUD V1", 2880, 1440)

# ----------------------------------------------------------------------------- Boucle While
while True:
    if time.time() - sys_update > 2.0:
        try:
            with open('/sys/devices/virtual/thermal/thermal_zone1/temp') as f:
                jetson_temp = int(f.read().strip()) / 1000
            cpu_percent = psutil.cpu_percent()
        except:
            pass
        sys_update = time.time()

    # Bascule nocturne automatique
    if NIGHT_VISION_AUTO_SWITCH and not NIGHT_VISION:
        if time.time() - t0 > NIGHT_VISION_DELAY:
            if night_switch_time == 0:
                cam_left.stop()
                cam_right.stop()
                night_switch_time = time.time()
                print("Arrêt caméras stéréo...")
            elif time.time() - night_switch_time > 1.0 and cam_night is None:
                cam_night = CameraThread(CAM_NIGHT)
                time.sleep(0.5)
                NIGHT_VISION = True
                print("Bascule vision nocturne")

    # Flux vision classique / vision nocturne
    if NIGHT_VISION:
        if cam_night is None or cam_night.frame is None:
            continue
        fl = cam_night.frame.copy()
        fr = cam_night.frame.copy()  # même flux sur les deux yeux
    else:
        if cam_left.frame is None or cam_right.frame is None:
            continue
        fl = cam_left.frame.copy()
        fr = cam_right.frame.copy()

    if len(fl.shape) == 2:
        fl = cv2.cvtColor(fl, cv2.COLOR_GRAY2BGR)
    if len(fr.shape) == 2:
        fr = cv2.cvtColor(fr, cv2.COLOR_GRAY2BGR)

    if time.time() - lat_update > 1.0:
        if not NIGHT_VISION and cam_left.timestamp:
            lat_display = (time.time() - cam_left.timestamp) * 1000
        lat_update = time.time()

    # Flux optique en alternance
    gray_l = cv2.cvtColor(fl, cv2.COLOR_BGR2GRAY)
    gray_r = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
    now_t = time.time()

    # Bloc detection de mouvement
    if count % 2 == 0:
        if prev_gray_l is not None:
            ml, mr = detect_motion_zone(prev_gray_l, gray_l)
            if ml > ZONE_SEUIL:
                alert_l_time = now_t
            if mr > ZONE_SEUIL:
                alert_r_time = now_t
        prev_gray_l = gray_l.copy()
    else:
        if prev_gray_r is not None:
            ml, mr = detect_motion_zone(prev_gray_r, gray_r)
            if ml > ZONE_SEUIL:
                alert_l_time = now_t
            if mr > ZONE_SEUIL:
                alert_r_time = now_t
        prev_gray_r = gray_r.copy()

    # Redimensionner l'affichage pour correspondre à l'écran 1440x1440p du module Wisecoco
    fl = cv2.resize(fl, (1440, 1440))
    fr = cv2.resize(fr, (1440, 1440))

    # Retourner le flux camera pour afficher dans le bon sens
    fl = cv2.flip(fl, -1)
    fr = cv2.flip(fr, -1)

    # Zone A - Navigation GPS et minimap
    if minimap_cache is None or abs(gps.lat - minimap_last_lat) > 0.0001 or abs(gps.lon - minimap_last_lon) > 0.0001:
        minimap_cache = get_minimap(gps.lat, gps.lon, zoom=14, size=250)
        minimap_last_lat = gps.lat
        minimap_last_lon = gps.lon
    fl[0:250, 0:250] = minimap_cache
    fr[0:250, 0:250] = minimap_cache

    # Zone B - Boussole et altimètre
    fl = draw_zone_b(fl, imu.roll, imu.pitch, imu.yaw, bme.pressure)
    fr = draw_zone_b(fr, imu.roll, imu.pitch, imu.yaw, bme.pressure)

    # Zone C - Données système
    fl = draw_zone_c(fl, fps, "ECRAN GAUCHE" if DEBUG else "", jetson_temp, cpu_percent, lat_display)
    fr = draw_zone_c(fr, fps, "ECRAN DROIT" if DEBUG else "", jetson_temp, cpu_percent, lat_display)
    
    # Zone Centre - réticule et horizon artificiel
    fl = draw_zone_centre(fl)
    fr = draw_zone_centre(fr)
    
    # Zone D/E - Flèches d'alerte
    fl = draw_zone_d(fl, now_t - alert_l_time < ALERT_DURATION)
    fr = draw_zone_d(fr, now_t - alert_l_time < ALERT_DURATION)
    fl = draw_zone_e(fl, now_t - alert_r_time < ALERT_DURATION, radar.targets)
    fr = draw_zone_e(fr, now_t - alert_r_time < ALERT_DURATION, radar.targets)

    # Zone G - OCR
    if ACTIVATE_OCR and count % 150 == 0:
        ocr.submit(cv2.flip(cam_left.frame.copy(), -1))
    ocr.poll()
    if SHOW_OCR:
        fl = draw_zone_g(fl, ocr.text)
        fr = draw_zone_g(fr, ocr.text)
    
    # Zone H - Données environnement
    fl = draw_zone_h(fl, bme.temperature, bme.humidity, bme.gas, bme.pressure)
    fr = draw_zone_h(fr, bme.temperature, bme.humidity, bme.gas, bme.pressure)

    # Zone I — Alerte critique gaz
        # Alerte présence gaz
    if bme.gas > 0 and bme.gas < SEUIL_RES_GAS:
        fl = draw_zone_i(fl, "!!! ALERTE GAZ !!!")
        fr = draw_zone_i(fr, "!!! ALERTE GAZ !!!")

        # Alerte température extérieure
    if bme.temperature > SEUIL_TEMP_EXT:
        fl = draw_zone_i(fl, f"!!! TEMP EXT {bme.temperature:.1f}C !!!", (0, 165, 255))
        fr = draw_zone_i(fr, f"!!! TEMP EXT {bme.temperature:.1f}C !!!", (0, 165, 255))

        # Alerte température Jetson
    if jetson_temp > SEUIL_TEMP_JETSON:
        fl = draw_zone_i(fl, f"!!! SURCHAUFFE JETSON {jetson_temp:.0f}C !!!", (0, 0, 255))
        fr = draw_zone_i(fr, f"!!! SURCHAUFFE JETSON {jetson_temp:.0f}C !!!", (0, 0, 255))

    # Affichage timestamp
    if DEBUG:
        fl = draw_timestamp_debug(fl)
        fr = draw_timestamp_debug(fr)

    # Jonction des deux frames cote à cote
    composite = np.hstack([fl, fr])

    count += 1
    fps = count / (time.time() - t0)

    # Affichage de la compisition de frame sur sortie vidéo
    composite = cv2.flip(composite, -1) # Flip horizontal + vertical
    cv2.imshow("IPES HUD V1", composite)
    # Capture auto après 10 secondes
    if count == 300 and DEBUG:  # ~10sec à 30fps
        cv2.imwrite(f'/tmp/ipes_capture_{int(time.time())}.png', composite)
        print("Capture sauvegardée !")

    if cv2.waitKey(1) & 0xFF == ord('q'):
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            cv2.imwrite(f'/tmp/ipes_capture_{int(time.time())}.png', composite)
            print(f"Capture sauvegardée")
            break

print(f"\nFPS pipeline complet : {fps:.1f}")
cam_left.stop()
cam_right.stop()
cv2.destroyAllWindows()
