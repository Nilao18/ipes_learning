#-----------------------------------------------------------------------------------
# Threads capteurs IPES - IMU, environnement, GPS, radar, cameras, clavier
#-----------------------------------------------------------------------------------
import math
import struct
import threading
import time

import cv2
import serial
import pynmea2
from adafruit_extended_bus import ExtendedI2C as I2C  # Import adafruit apres le reset
from adafruit_bno08x.i2c import BNO08X_I2C
from adafruit_bno08x import BNO_REPORT_ROTATION_VECTOR
import adafruit_bme680

import hud_config as cfg


#------------------------------------------------------------------------------------
# Thread IMU (BNO085) - Inertial Measurement Unit : Pitch, Yaw, Roll
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
# Thread BME (BME688) - Capteur de temperature, humidite et gaz
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
# Thread GPS (MAX-M10S) - Position en temps reel, NMEA 9600 bauds
#-----------------------------------------------------------------------------------
class GPSThread:
    def __init__(self):
        print("Init GPS...")
        self.ser = serial.Serial(cfg.GPS_PORT, 9600, timeout=2)
        self.lat = 47.3941  # position par defaut Tours
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
                        self.speed = float(msg.spd_over_grnd) * 1.852  # kts -> km/h
            except Exception:
                pass

    def stop(self):
        self.running = False
        self.ser.close()


#-----------------------------------------------------------------------------------
# Thread HLK-LD2450 - Radar 24 GHz, jusqu'a 3 cibles, coordonnees en metres
#-----------------------------------------------------------------------------------
class RadarThread:
    def __init__(self):
        print("Init Radar...")
        self.ser = serial.Serial(cfg.RADAR_PORT, 256000, timeout=1)
        self.targets = []
        self._dist_history = []
        self.smooth_dist = 0.0
        self.running = True
        self.thread = threading.Thread(target=self.update)
        self.thread.daemon = True
        self.thread.start()
        print("Radar OK")

    def _decode_coord(self, raw):
        """Format LD2450 : bit 15 = signe, 15 bits de valeur en mm -> metres."""
        sign = -1 if (raw & 0x8000) else 1
        return sign * (raw & 0x7FFF) / 1000.0

    def update(self):
        buf = bytearray()
        while self.running:
            try:
                buf += self.ser.read(64)
                # Recherche de l'entete AA FF
                start = -1
                for i in range(len(buf) - 1):
                    if buf[i] == 0xAA and buf[i+1] == 0xFF:
                        start = i
                        break
                if start == -1:
                    if len(buf) > 512:
                        buf = bytearray()
                    continue
                # Recherche du pied de trame 55 CC
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

                # Lissage sur 10 mesures de la cible la plus proche
                if targets:
                    closest = min(targets, key=lambda t: t['x']**2 + t['y']**2)
                    dist = (closest['x']**2 + closest['y']**2) ** 0.5
                    self._dist_history.append(dist)
                    if len(self._dist_history) > 10:
                        self._dist_history.pop(0)
                    self.smooth_dist = sum(self._dist_history) / len(self._dist_history)
            except Exception as e:
                print(f"Radar erreur: {e}")

    def stop(self):
        self.running = False
        self.ser.close()


#-----------------------------------------------------------------------------------
# Thread Camera - Capture UVC, MJPG obligatoire pour le 720p sur l'IMX462
#-----------------------------------------------------------------------------------
class CameraThread:
    def __init__(self, device, width=1280, height=720, period=0.0):
        """period > 0 : temporisation entre captures, limite la charge CPU et USB."""
        self.cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.period = period
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
            if self.period > 0:
                time.sleep(self.period)

    def stop(self):
        self.running = False
        self.thread.join(timeout=2)
        self.cap.release()


#-----------------------------------------------------------------------------------
# Thread INPUT - Entrees clavier depuis le terminal SSH
#-----------------------------------------------------------------------------------
class KeyboardThread:
    def __init__(self):
        self.key = None
        self.running = True
        self.thread = threading.Thread(target=self.update)
        self.thread.daemon = True
        self.thread.start()

    def update(self):
        import sys
        while self.running:
            line = sys.stdin.readline().strip()
            if line:
                self.key = line[0]

    def get(self):
        """Retourne la derniere touche saisie puis la consomme."""
        k = self.key
        self.key = None
        return k
