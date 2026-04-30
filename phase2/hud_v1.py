import cv2
import numpy as np
import threading
import time
from datetime import datetime
import math
import os
from PIL import Image

# Import adafruit après le reset
from adafruit_extended_bus import ExtendedI2C as I2C
from adafruit_bno08x.i2c import BNO08X_I2C
from adafruit_bno08x import BNO_REPORT_ROTATION_VECTOR
import adafruit_bme680

DEBUG = False #True pour afficher FPS/LAT
SHOW_RETICULE = False
SHOW_HORIZON = False
SHOW_COMPASS = True
SHOW_ALTITUDE = True

TILES_DIR = "/home/quentin/ipes/maps/tours"

class IMUThread:
    def __init__(self):
        print("Init IMU...")
        i2c = I2C(7)
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

class BMEThread:
    def __init__(self):
        print("Init BME688...")
        i2c = I2C(1)
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

def detect_motion_zone(prev_gray, gray, seuil=10):
    small_prev = cv2.resize(prev_gray, (160, 90))
    small_gray = cv2.resize(gray, (160, 90))
    diff = cv2.absdiff(small_prev, small_gray)
    _, thresh = cv2.threshold(diff, seuil, 255, cv2.THRESH_BINARY)
    w = thresh.shape[1]
    motion_left  = np.sum(thresh[:, :w//2]) / 255
    motion_right = np.sum(thresh[:, w//2:]) / 255
    return motion_left, motion_right

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

def get_minimap(lat, lon, zoom=14, size=400):
    x_tile, y_tile = deg2tile(lat, lon, zoom)
    
    # Charger 3x3 tuiles autour de la position
    canvas = np.zeros((size, size, 3), dtype=np.uint8)
    tile_size = 256
    
    for dx in range(-1, 2):
        for dy in range(-1, 2):
            tx = x_tile + dx
            ty = y_tile + dy
            path = os.path.join(TILES_DIR, str(zoom), str(tx), f"{ty}.png")
            
            if not os.path.exists(path):
                continue
            
            img = np.array(Image.open(path).convert('RGB'))
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            
            # Position sur le canvas
            cx = size//2 + dx * tile_size
            cy = size//2 + dy * tile_size
            
            # Clip et colle
            x1 = max(0, cx - tile_size//2)
            y1 = max(0, cy - tile_size//2)
            x2 = min(size, cx + tile_size//2)
            y2 = min(size, cy + tile_size//2)
            
            sx1 = max(0, tile_size//2 - cx)
            sy1 = max(0, tile_size//2 - cy)
            
            if x2 > x1 and y2 > y1:
                canvas[y1:y2, x1:x2] = img[sy1:sy1+(y2-y1), sx1:sx1+(x2-x1)]
    
    # Marqueur position (triangle)
    cv2.circle(canvas, (size//2, size//2), 6, (0, 0, 255), -1)
    cv2.circle(canvas, (size//2, size//2), 8, (255, 255, 255), 2)
    
    return canvas

def deg2tile(lat, lon, zoom):
    lat_r = math.radians(lat)
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(lat_r) + 1/math.cos(lat_r)) / math.pi) / 2 * n)
    return x, y

def draw_zone_a(frame, lat, lon, zoom=14):
    h, w = frame.shape[:2]
    
    minimap = get_minimap(lat, lon, zoom=zoom, size=200)
    
    # Bordure zone A
    cv2.rectangle(minimap, (0, 0), (199, 199), (0, 150, 0), 1)
    cv2.putText(minimap, "NAV", (5, 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 150, 0), 1)
    
    # Coller en haut gauche
    frame[0:200, 0:200] = minimap
    
    return frame

def draw_zone_b(frame, roll, pitch, yaw, pressure=1013.25):
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

    h, w = frame.shape[:2]
    cx = w // 2
    compass_w = w // 2
    
    color_large = (255, 255, 255)
    color_small = (0, 200, 0)
    color_dim = (0, 150, 0)
    
    compass_left  = cx - compass_w//2 - 10  # juste à gauche de la boussole
    compass_right = cx + compass_w//2 + 10  # juste à droite

    if SHOW_ALTITUDE:
        # Curseur gauche = pieds
        cv2.putText(frame, "FT", (compass_left - 25, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, color_dim, 2)
        cv2.putText(frame, f"{alt_ft:.0f}", (compass_left - 30, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_large, 2)

        # Curseur droit = mètres
        cv2.putText(frame, "M", (compass_right + 15, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, color_dim, 2)
        cv2.putText(frame, f"{alt_m:.0f}", (compass_right + 5, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_large, 2)
    
        # Graduation verticale altitude — gauche (pieds)
        grad_h = 200  # hauteur totale de la graduation
        grad_x_l = compass_left - 45
        grad_y_center = 120  # centre vertical
        cv2.line(frame, (grad_x_l, grad_y_center - grad_h//2),
             (grad_x_l, grad_y_center + grad_h//2), color_dim, 2)

        for i in range(-5, 6):
            y = grad_y_center + i * 20
            if i % 5 == 0:
                cv2.line(frame, (grad_x_l - 8, y), (grad_x_l, y), color_large, 3)
                cv2.putText(frame, f"{int(alt_ft - i*50)}", (grad_x_l - 50, y+5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 2)
            else:
                cv2.line(frame, (grad_x_l - 4, y), (grad_x_l, y), color_small, 2)

        # Graduation verticale altitude — droite (mètres)
        grad_x_r = compass_right + 45
        cv2.line(frame, (grad_x_r, grad_y_center - grad_h//2),
             (grad_x_r, grad_y_center + grad_h//2), color_dim, 2)

        for i in range(-5, 6):
            y = grad_y_center + i * 20
            if i % 5 == 0:
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

def draw_zone_c(frame, fps):
    h, w = frame.shape[:2]
    # Zone C : haut droite 200x200px
    x = w - 195
    y = 10
    color_dim = (0, 150, 0)
    now = datetime.now()

    cv2.putText(frame, now.strftime("%H:%M:%S"), (x, y+20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_dim, 1)
    cv2.putText(frame, now.strftime("%d/%m/%Y"), (x, y+45),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, color_dim, 1)

    if DEBUG:
        cv2.putText(frame, f"FPS:{fps:.1f}", (x, y+68),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color_dim, 1)

    return frame

def draw_zone_d(frame, alert_active):
    if not alert_active:
        return frame
    h, w = frame.shape[:2]
    # Zone D : centre gauche, 200px de large
    cx_d = 100  # centre de la zone D
    cy = h // 2
    # Flèche principale
    cv2.arrowedLine(frame, (190, cy), (30, cy), (0, 0, 255), 8, tipLength=0.4)
    # Texte alerte
    cv2.putText(frame, "MVT", (20, cy - 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    return frame

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

def draw_zone_e(frame, alert_active):
    if not alert_active:
        return frame
    h, w = frame.shape[:2]
    cx_e = w - 100  # centre de la zone E
    cy = h // 2
    # Flèche principale
    cv2.arrowedLine(frame, (w - 190, cy), (w - 30, cy), (0, 0, 255), 8, tipLength=0.4)
    # Texte alerte
    cv2.putText(frame, "MVT", (w - 70, cy - 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    return frame

def draw_zone_h(frame, temperature, humidity, gas):
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
    cv2.putText(frame, "ENV", (x+8, y+20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 1)
    
    # Température
    cv2.putText(frame, "TEMP", (x+8, y+42),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 1)
    cv2.putText(frame, f"{temperature:.1f}C", (x+8, y+68),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    
    # Humidité
    cv2.putText(frame, "HUM", (x+8, y+98),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 200, 0), 1)
    cv2.putText(frame, f"{humidity:.0f}%", (x+8, y+124),
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

    cv2.putText(frame, "GAZ", (x+8, y+150),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 200, 0), 1)
    cv2.putText(frame, gaz_label, (x+8, y+174),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, gaz_color, 2)
    cv2.putText(frame, f"{gas//1000}k ohm", (x+8, y+198),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 1)
    
    return frame

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

CAM_LEFT  = "/dev/v4l/by-path/platform-3610000.usb-usb-0:2.1:1.0-video-index0"
CAM_RIGHT = "/dev/v4l/by-path/platform-3610000.usb-usb-0:2.2:1.0-video-index0"

cam_left  = CameraThread(CAM_LEFT)
time.sleep(0.5)
cam_right = CameraThread(CAM_RIGHT)
time.sleep(1)
imu = IMUThread()
time.sleep(1)
bme = BMEThread()
time.sleep(1)

t0 = time.time()
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

cv2.namedWindow("IPES HUD V1", cv2.WINDOW_NORMAL)
cv2.setWindowProperty("IPES HUD V1", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
cv2.resizeWindow("IPES HUD V1", 2880, 1440)

while True:
    if cam_left.frame is None or cam_right.frame is None:
        continue

    fl = cam_left.frame.copy()
    fr = cam_right.frame.copy()

    if len(fl.shape) == 2:
        fl = cv2.cvtColor(fl, cv2.COLOR_GRAY2BGR)
    if len(fr.shape) == 2:
        fr = cv2.cvtColor(fr, cv2.COLOR_GRAY2BGR)

    if time.time() - lat_update > 1.0:
        lat_display = (time.time() - cam_left.timestamp) * 1000
        lat_update = time.time()

    # Flux optique en alternance
    gray_l = cv2.cvtColor(fl, cv2.COLOR_BGR2GRAY)
    gray_r = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
    now_t = time.time()

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

    fl = cv2.resize(fl, (1440, 1440))
    fr = cv2.resize(fr, (1440, 1440))

    fl = draw_zone_a(fl, 47.3941, 0.6848)
    fr = draw_zone_a(fr, 47.3941, 0.6848)

    fl = draw_zone_b(fl, imu.roll, imu.pitch, imu.yaw, bme.pressure)
    fr = draw_zone_b(fr, imu.roll, imu.pitch, imu.yaw, bme.pressure)

    fl = draw_zone_c(fl, fps)
    fr = draw_zone_c(fr, fps)

    fl = draw_zone_centre(fl)
    fr = draw_zone_centre(fr)

    fl = draw_zone_h(fl, bme.temperature, bme.humidity, bme.gas)
    fr = draw_zone_h(fr, bme.temperature, bme.humidity, bme.gas)
    
    # Flèches d'alerte
    fl = draw_zone_d(fl, now_t - alert_l_time < ALERT_DURATION)
    fr = draw_zone_d(fr, now_t - alert_l_time < ALERT_DURATION)
    fl = draw_zone_e(fl, now_t - alert_r_time < ALERT_DURATION)
    fr = draw_zone_e(fr, now_t - alert_r_time < ALERT_DURATION)

    # Zone I — alerte critique gaz
    if bme.gas > 0 and bme.gas < 20000:
        fl = draw_zone_i(fl, "!!! ALERTE GAZ !!!")
        fr = draw_zone_i(fr, "!!! ALERTE GAZ !!!")

    composite = np.hstack([fl, fr])

    count += 1
    fps = count / (time.time() - t0)

    cv2.imshow("IPES HUD V1", composite)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

print(f"\nFPS pipeline complet : {fps:.1f}")
cam_left.stop()
cam_right.stop()
cv2.destroyAllWindows()
