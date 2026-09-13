#-----------------------------------------------------------------------------------
# Threads capteurs IPES - IMU, environnement, GPS, radar, cameras, clavier
#-----------------------------------------------------------------------------------
import json
import math
import struct
import threading
import time

import cv2
import serial
import pynmea2
from adafruit_extended_bus import ExtendedI2C as I2C  # Import adafruit apres le reset
import adafruit_bme680

import hud_config as cfg


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
# Base des capteurs serie USB (FT232) - reconnexion automatique apres debranchement
#-----------------------------------------------------------------------------------
class _SerieUSB:
    """Un port absent ou perdu ne leve jamais d'exception : le thread retente toutes
    les SERIE_RECO secondes au lieu de boucler sur l'erreur (un coeur a 100 %)."""

    def _init_serie(self, nom, port, baud, timeout):
        self.nom, self.port, self.baud, self.timeout = nom, port, baud, timeout
        self.ser = None
        self.connecte = False
        if not self._connecter():
            print(f"{nom} absent, nouvel essai toutes les {cfg.SERIE_RECO:.0f} s")

    def _connecter(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
            self.connecte = True
            return True
        except (serial.SerialException, OSError):
            self.ser, self.connecte = None, False
            return False

    def _deconnecter(self, e):
        """Port perdu : fermeture propre et donnees remises a zero (pas de valeurs figees)."""
        print(f"{self.nom} deconnecte ({e}), reconnexion automatique")
        try:
            self.ser.close()
        except Exception:
            pass
        self.ser, self.connecte = None, False
        self._perte()

    def _attendre_port(self):
        """True si le port est utilisable ; sinon une tentative puis pause."""
        if self.ser is not None:
            return True
        if self._connecter():
            print(f"{self.nom} reconnecte")
            return True
        time.sleep(cfg.SERIE_RECO)
        return False

    def stop(self):
        self.running = False
        if self.ser is not None:
            self.ser.close()


#-----------------------------------------------------------------------------------
# Thread Casque (ESP32-S3 sur ttyTHS1) - orientation 50 Hz et commandes acquittees
#-----------------------------------------------------------------------------------
class CasqueThread(_SerieUSB):
    """Liaison JSON avec l'ESP32 du casque : une trame par ligne.
    Recoit le quaternion du BNO085 ; la conversion en angles reste ici, a l'identique
    de l'ancien IMUThread, pour ne pas dupliquer la convention entre les deux cartes."""

    def __init__(self):
        print("Init Casque (ESP32)...")
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        self.etat_imu = 0          # qualite d'etalonnage BNO085, 0 a 3
        self.derniere_imu = 0.0    # horodatage de la derniere trame recue
        self._acks = {}            # id de commande -> True/False
        self._id = 0
        self._lock = threading.Lock()
        self._init_serie("Casque", cfg.CASQUE_PORT, cfg.CASQUE_BAUD, 1)
        if self.connecte:
            self.ser.reset_input_buffer()   # octets parasites de l'ouverture du port
        self.running = True
        self.thread = threading.Thread(target=self.update)
        self.thread.daemon = True
        self.thread.start()
        print("Casque OK" if self.connecte else "Casque demarre sans port")

    @property
    def imu_ok(self):
        """False si le casque ne parle plus : l'horizon et le POI sont alors figes."""
        return self.connecte and (time.time() - self.derniere_imu) < cfg.CASQUE_TIMEOUT

    def _perte(self):
        self.etat_imu = 0
        with self._lock:
            self._acks.clear()

    def commande(self, cible, valeur=0, attendre=True):
        """Envoie une commande au casque. Retourne True si acquittee, False sinon."""
        if not self.connecte:
            return False
        with self._lock:
            self._id += 1
            ident = self._id
        trame = json.dumps({"t": "cmd", "id": ident, "cible": cible, "val": valeur})
        try:
            self.ser.write((trame + "\n").encode())
        except (serial.SerialException, OSError) as e:
            self._deconnecter(e)
            return False
        if not attendre:
            return True
        limite = time.time() + cfg.CASQUE_ACK
        while time.time() < limite:
            with self._lock:
                if ident in self._acks:
                    return self._acks.pop(ident)
            time.sleep(0.005)
        print("Casque : pas d'accuse pour la commande", cible)
        return False

    def _traiter(self, msg):
        type_msg = msg.get("t")
        if type_msg == "imu":
            qi, qj, qk = msg["qi"], msg["qj"], msg["qk"]
            real = msg["qr"]
            self.roll = math.degrees(math.atan2(2 * (real * qi + qj * qk),
                                                1 - 2 * (qi * qi + qj * qj)))
            self.pitch = math.degrees(math.asin(max(-1, min(1, 2 * (real * qj - qk * qi)))))
            self.yaw = math.degrees(math.atan2(2 * (real * qk + qi * qj),
                                               1 - 2 * (qj * qj + qk * qk)))
            self.etat_imu = msg.get("st", 0)
            self.derniere_imu = time.time()
        elif type_msg == "ack":
            with self._lock:
                self._acks[msg.get("id")] = bool(msg.get("ok"))
        elif type_msg == "err":
            print("Casque erreur :", msg.get("msg"))

    def update(self):
        while self.running:
            if not self._attendre_port():
                continue
            try:
                ligne = self.ser.readline().decode('utf-8', errors='replace').strip()
            except (serial.SerialException, OSError) as e:
                self._deconnecter(e)
                continue
            if not ligne:
                continue
            try:
                self._traiter(json.loads(ligne))
            except (ValueError, KeyError, TypeError):
                pass    # trame tronquee ou champ manquant : on passe a la suivante


#-----------------------------------------------------------------------------------
# Thread GPS (MAX-M10S) - Position en temps reel, NMEA 9600 bauds
#-----------------------------------------------------------------------------------
class GPSThread(_SerieUSB):
    def __init__(self):
        print("Init GPS...")
        self.lat = 47.3941  # position par defaut Tours
        self.lon = 0.6848
        self.alt = 0.0
        self.speed = 0.0
        self.satellites = 0
        self.hdop = 99.99   # precision horizontale, 99.99 = inconnue
        self.fix = False
        self._init_serie("GPS", cfg.GPS_PORT, 9600, 2)
        self.running = True
        self.thread = threading.Thread(target=self.update)
        self.thread.daemon = True
        self.thread.start()
        print("GPS OK" if self.connecte else "GPS demarre sans port")

    def _perte(self):
        self.fix = False
        self.satellites = 0
        self.hdop = 99.99

    def update(self):
        while self.running:
            if not self._attendre_port():
                continue
            try:
                line = self.ser.readline().decode('ascii', errors='replace').strip()
                if line.startswith('$GNGGA'):
                    msg = pynmea2.parse(line)
                    self.satellites = int(msg.num_sats or 0)
                    self.hdop = float(msg.horizontal_dil) if msg.horizontal_dil else 99.99
                    self.fix = int(msg.gps_qual) > 0
                    if self.fix:
                        self.alt = float(msg.altitude) if msg.altitude else 0.0
                elif line.startswith('$GNRMC'):
                    msg = pynmea2.parse(line)
                    if msg.status == 'A':
                        self.lat = msg.latitude
                        self.lon = msg.longitude
                        self.speed = float(msg.spd_over_grnd) * 1.852  # kts -> km/h
            except (serial.SerialException, OSError) as e:
                self._deconnecter(e)
            except Exception:
                pass    # trame NMEA corrompue : on passe a la suivante


#-----------------------------------------------------------------------------------
# Thread HLK-LD2450 - Radar 24 GHz, jusqu'a 3 cibles, coordonnees en metres
#-----------------------------------------------------------------------------------
class RadarThread(_SerieUSB):
    def __init__(self):
        print("Init Radar...")
        self.targets = []
        self._dist_history = []
        self.smooth_dist = 0.0
        self._init_serie("Radar", cfg.RADAR_PORT, 256000, 1)
        self.running = True
        self.thread = threading.Thread(target=self.update)
        self.thread.daemon = True
        self.thread.start()
        print("Radar OK" if self.connecte else "Radar demarre sans port")

    def _perte(self):
        self.targets = []           # surtout pas de cibles figees a l'ecran
        self._dist_history = []
        self.smooth_dist = 0.0

    def _decode_coord(self, raw):
        """Format LD2450 : bit 15 a 1 = positif (inverse du complement a 2), 15 bits en mm -> metres."""
        sign = 1 if (raw & 0x8000) else -1
        return sign * (raw & 0x7FFF) / 1000.0

    def update(self):
        buf = bytearray()
        while self.running:
            if not self._attendre_port():
                buf = bytearray()
                continue
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
            except (serial.SerialException, OSError) as e:
                self._deconnecter(e)
                buf = bytearray()
            except Exception as e:
                print(f"Radar erreur: {e}")


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
        import os
        import sys
        # Rangee des chiffres AZERTY sans Maj : & e " ' ( donnent 1 a 5
        azerty = {'&': '1', '\u00e9': '2', '"': '3', "'": '4', '(': '5'}
        while self.running:
            try:
                brut = os.read(sys.stdin.fileno(), 1024)   # non bufferise : pas de verrou bloquant a l'arret
                if not brut:                 # fin de flux (pas de terminal) : pas de boucle a vide
                    time.sleep(0.5)
                    continue
                try:
                    line = brut.decode('utf-8').strip()
                except UnicodeDecodeError:   # terminal en latin-1 ou octet parasite
                    line = brut.decode('latin-1').strip()
            except Exception:
                time.sleep(0.1)              # le thread clavier ne doit jamais mourir
                continue
            if line:
                self.key = azerty.get(line[0], line[0])

    def get(self):
        """Retourne la derniere touche saisie puis la consomme."""
        k = self.key
        self.key = None
        return k
