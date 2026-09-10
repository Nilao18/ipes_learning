#-----------------------------------------------------------------------------------
# Rendu HUD - minimap, boussole, horizon et zones d'affichage
#-----------------------------------------------------------------------------------
# Toutes les fonctions dessinent en place dans "frame" et le retournent.
# L'etat variable (MODE, poi) est lu via cfg.<nom> pour suivre les changements.
import math
import os
from datetime import datetime

import cv2
import numpy as np
from PIL import Image

import hud_config as cfg


#------------------------------------------------------------------------------ Affichage horizon artificiel
def draw_horizon(frame, roll, pitch):
    h, w = frame.shape[:2]
    cx, cy = w // 2, h // 2
    color = (0, 255, 0)

    # Decalage vertical selon le pitch
    pitch_offset = int(pitch * 4)
    length = w // 2

    # Calcul des extremites selon le roll
    angle_rad = math.radians(roll)
    dx = int(length * math.cos(angle_rad))
    dy = int(length * math.sin(angle_rad))

    x1, y1 = cx - dx, cy + pitch_offset + dy
    x2, y2 = cx + dx, cy + pitch_offset - dy
    cv2.line(frame, (x1, y1), (x2, y2), color, 3)

    # Marqueur centre fixe (repere casque)
    cv2.line(frame, (cx - 60, cy), (cx - 20, cy), (255, 255, 255), 3)
    cv2.line(frame, (cx + 20, cy), (cx + 60, cy), (255, 255, 255), 3)
    cv2.circle(frame, (cx, cy), 5, (255, 255, 255), -1)
    return frame


#----------------------------------------------------------------------Affichage boussole
def draw_compass(frame, yaw):
    h, w = frame.shape[:2]
    cx = w // 2
    compass_y = 40
    compass_w = w // cfg.COMPASS_DIV.get(cfg.MODE, 3) + 50
    deg_per_px = compass_w / 60.0  # 60 deg visibles au total

    color_small = (0, 200, 0)
    color_large = (255, 255, 255)
    color_cardinal = (0, 200, 255)

    cardinals = {0: 'N', 45: 'NE', 90: 'E', 135: 'SE',
                 180: 'S', 225: 'SO', 270: 'O', 315: 'NO'}

    # Ligne de base
    cv2.line(frame, (cx - compass_w//2, compass_y),
             (cx + compass_w//2, compass_y), color_small, 2)

    # Graduations centrees sur le cap courant
    for deg in range(0, 360):
        diff = (deg - yaw + 180) % 360 - 180
        if abs(diff) > 30:  # 30 deg de chaque cote = 60 deg visibles
            continue
        px = cx + int(diff * deg_per_px)

        if deg % 45 == 0:
            # Grand trait + cardinal
            cv2.line(frame, (px, compass_y - 5), (px, compass_y + 25), color_cardinal, 3)
            cv2.putText(frame, cardinals.get(deg, ''), (px - 12, compass_y + 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_cardinal, 3)
        elif deg % 10 == 0:
            # Trait moyen + chiffre
            cv2.line(frame, (px, compass_y - 3), (px, compass_y + 18), color_large, 2)
            cv2.putText(frame, str(deg), (px - 10, compass_y + 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_large, 2)
        elif deg % 5 == 0:
            cv2.line(frame, (px, compass_y), (px, compass_y + 12), color_small, 2)
        else:
            cv2.line(frame, (px, compass_y), (px, compass_y + 6), color_small, 2)

    # Marqueur cap fixe (triangle)
    pts = np.array([[cx, compass_y - 4], [cx - 12, compass_y - 16], [cx + 12, compass_y - 16]])
    cv2.fillPoly(frame, [pts], color_large)
    return frame


#---------------------------------------------------------------------------- Chargement de la minimap
def get_minimap(lat, lon, zoom=14, size=250):
    x_tile, y_tile = deg2tile(lat, lon, zoom)
    tile_size = 256

    # Position exacte en pixels dans la tuile
    n = 2 ** zoom
    lat_r = math.radians(lat)
    px_exact = (lon + 180) / 360 * n * tile_size
    py_exact = (1 - math.log(math.tan(lat_r) + 1/math.cos(lat_r)) / math.pi) / 2 * n * tile_size

    # Decalage par rapport au coin de la tuile centrale
    px_in_tile = px_exact - x_tile * tile_size
    py_in_tile = py_exact - y_tile * tile_size

    canvas = np.zeros((size, size, 3), dtype=np.uint8)

    for dx in range(-1, 2):
        for dy in range(-1, 2):
            tx, ty = x_tile + dx, y_tile + dy
            path = os.path.join(cfg.TILES_DIR, str(zoom), str(tx), f"{ty}.png")
            if not os.path.exists(path):
                continue
            img = np.array(Image.open(path).convert('RGB'))
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

            # Centre du canvas = position exacte GPS
            cx = size//2 + dx * tile_size - int(px_in_tile)
            cy = size//2 + dy * tile_size - int(py_in_tile)

            x1, y1 = max(0, cx), max(0, cy)
            x2, y2 = min(size, cx + tile_size), min(size, cy + tile_size)
            sx1, sy1 = max(0, -cx), max(0, -cy)

            if x2 > x1 and y2 > y1:
                canvas[y1:y2, x1:x2] = img[sy1:sy1+(y2-y1), sx1:sx1+(x2-x1)]

    # Marqueur position au centre exact
    cv2.circle(canvas, (size//2, size//2), 6, (0, 0, 255), -1)
    cv2.circle(canvas, (size//2, size//2), 8, (255, 255, 255), 2)
    return canvas


#----------------------------------- Conversion coordonnees GPS vers position sur tuile minimap
def deg2tile(lat, lon, zoom):
    lat_r = math.radians(lat)
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(lat_r) + 1/math.cos(lat_r)) / math.pi) / 2 * n)
    return x, y


# --------------------------------------------------------------------------------Affichage de la Zone B
def draw_zone_b(frame, roll, pitch, yaw, pressure=1013.25):
    h, w = frame.shape[:2]
    cx = w // 2
    compass_w = w // cfg.COMPASS_DIV.get(cfg.MODE, 3) + 50

    # Fond semi-transparent derriere boussole et altimetres
    overlay = frame.copy()
    if cfg.SHOW_COMPASS:
        cv2.rectangle(overlay,
                      (cx - compass_w//2 - 5, 0),
                      (cx + compass_w//2 + 5, 95),
                      (0, 0, 0), -1)
    if cfg.SHOW_ALTITUDE and cfg.MODE != "MINIMAL":
        # Fond derriere curseur gauche (pieds)
        cv2.rectangle(overlay,
                      (cx - compass_w//2 - 110, 0),
                      (cx - compass_w//2, 240),
                      (0, 0, 0), -1)
        # Fond derriere curseur droit (metres)
        cv2.rectangle(overlay,
                      (cx + compass_w//2, 0),
                      (cx + compass_w//2 + 110, 240),
                      (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

    # Horizon artificiel
    if cfg.SHOW_HORIZON:
        frame = draw_horizon(frame, roll, pitch)

    # Boussole
    COMPASS_OFFSET = -45
    if cfg.SHOW_COMPASS:
        frame = draw_compass(frame, (-yaw + COMPASS_OFFSET) % 360)

    # Altitude barometrique
    alt_m = 44330 * (1 - (pressure / 1013.25) ** 0.1903)
    alt_ft = alt_m * 3.28084

    color_large = (255, 255, 255)
    color_small = (0, 200, 0)
    color_dim = (0, 150, 0)

    compass_left  = cx - compass_w//2 - 10
    compass_right = cx + compass_w//2 + 10

    if cfg.SHOW_ALTITUDE and cfg.MODE != "MINIMAL":
        cv2.putText(frame, "FT", (compass_left - 60, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 2)
        cv2.putText(frame, "M", (compass_right + 50, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 2)

        # Graduation verticale gauche (pieds)
        grad_h = 175
        grad_x_l = compass_left - 5
        grad_y_center = 120
        cv2.line(frame, (grad_x_l, grad_y_center - grad_h//2),
                 (grad_x_l, grad_y_center + grad_h//2), color_dim, 2)

        for i in range(-5, 6):
            y = grad_y_center + i * 17
            if i == 0:
                # Valeur reelle : trait epais + texte blanc
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

        # Graduation verticale droite (metres)
        grad_x_r = compass_right + 5
        cv2.line(frame, (grad_x_r, grad_y_center - grad_h//2),
                 (grad_x_r, grad_y_center + grad_h//2), color_dim, 2)

        for i in range(-5, 6):
            y = grad_y_center + i * 17
            if i == 0:
                cv2.line(frame, (grad_x_r + 12, y), (grad_x_r, y), color_large, 3)
                cv2.putText(frame, f"{int(alt_ft)}", (grad_x_r + 20, y + 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_large, 2)
            elif i % 5 == 0:
                cv2.line(frame, (grad_x_r, y), (grad_x_r + 8, y), color_large, 3)
                cv2.putText(frame, f"{int(alt_m - i*15)}", (grad_x_r + 20, y+5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 2)
            else:
                cv2.line(frame, (grad_x_r, y), (grad_x_r + 4, y), color_small, 2)

    # R/P/Y sous la boussole
    if cfg.DEBUG:
        cv2.putText(frame, f"R:{roll:6.1f}", (cx, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 1)
        cv2.putText(frame, f"P:{pitch:6.1f}", (cx, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 1)
        cv2.putText(frame, f"Y:{yaw:6.1f}", (cx, 140),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 1)

    # Marqueur POI sur la boussole
    if cfg.poi is not None:
        dpp = compass_w / 60.0
        d = cfg.poi["yaw"] - yaw
        while d > 180:
            d -= 360
        while d < -180:
            d += 360
        if abs(d) < 30:
            mx = cx + int(d * dpp)
            cv2.drawMarker(frame, (mx, 62), cfg.POI_COLOR,
                           cv2.MARKER_TRIANGLE_DOWN, 14, 2)
    return frame


# --------------------------------------------------------------------------------Affichage de la Zone C
def draw_zone_c(frame, fps, side="", jetson_temp=0, cpu=0, lat=0):
    x, y = 110, 10
    color_dim = (0, 150, 0)
    now = datetime.now()

    cv2.putText(frame, now.strftime("%H:%M:%S"), (x, y+20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color_dim, 2)

    if cfg.MODE not in ("MINIMAL", "OFF"):
        cv2.putText(frame, now.strftime("%d/%m/%Y"), (x, y+50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color_dim, 2)
        temp_color = (0, 0, 255) if jetson_temp > 75 else color_dim
        cv2.putText(frame, f"CPU:{cpu:.0f}%", (x, y+80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color_dim, 2)
        cv2.putText(frame, f"T:{jetson_temp:.0f}C", (x, y+110),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, temp_color, 2)

    cv2.putText(frame, cfg.MODE, (x, y+140),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)

    # Debug FPS + latence
    if cfg.DEBUG:
        cv2.putText(frame, f"FPS:{fps:.1f}", (x, y+170),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_dim, 2)
        cv2.putText(frame, f"LAT:{lat:.0f}ms", (x, y+190),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_dim, 2)
        cv2.putText(frame, side, (x, y+210),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_dim, 2)
    return frame


# --------------------------------------------------------------------------------Affichage de la Zone D
def draw_zone_d(frame, alert_active):
    if not alert_active:
        return frame
    h, w = frame.shape[:2]
    cy = h // 2
    cv2.arrowedLine(frame, (190, cy), (30, cy), (0, 0, 255), 8, tipLength=0.4)
    cv2.putText(frame, "PERS", (20, cy - 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    return frame


# --------------------------------------------------------------------------------Affichage de la Zone CENTRE
def draw_poi(frame, yaw, pitch):
    """Cercle de verrouillage POI, ou fleche de bord si hors champ."""
    if cfg.poi is None:
        return frame
    h, w = frame.shape[:2]
    cx, cy = w // 2, h // 2

    dyaw = cfg.poi["yaw"] - yaw
    while dyaw > 180:
        dyaw -= 360
    while dyaw < -180:
        dyaw += 360
    dpitch = cfg.poi["pitch"] - pitch

    px = int(cx + dyaw * cfg.PX_PER_DEG_X)
    py = int(cy - dpitch * cfg.PX_PER_DEG_Y)
    m = 45

    if m < px < w - m and m < py < h - m:
        # POI dans le champ : cercle + croix de visee
        cv2.circle(frame, (px, py), 28, cfg.POI_COLOR, 2)
        cv2.circle(frame, (px, py), 3, cfg.POI_COLOR, -1)
        cv2.line(frame, (px-40, py), (px-34, py), cfg.POI_COLOR, 2)
        cv2.line(frame, (px+34, py), (px+40, py), cfg.POI_COLOR, 2)
        cv2.line(frame, (px, py-40), (px, py-34), cfg.POI_COLOR, 2)
        cv2.line(frame, (px, py+34), (px, py+40), cfg.POI_COLOR, 2)
    else:
        # POI hors champ : fleche plaquee au bord
        ex = min(max(px, m), w - m)
        ey = min(max(py, m), h - m)
        ang = math.atan2(py - cy, px - cx)
        pts = np.array([
            (int(ex + 20*math.cos(ang)),     int(ey + 20*math.sin(ang))),
            (int(ex + 20*math.cos(ang+2.5)), int(ey + 20*math.sin(ang+2.5))),
            (int(ex + 20*math.cos(ang-2.5)), int(ey + 20*math.sin(ang-2.5))),
        ])
        cv2.fillPoly(frame, [pts], cfg.POI_COLOR)
    return frame


def draw_vignettes(frame, det):
    """Imagettes des personnes detectees, cote correspondant."""
    h, w = frame.shape[:2]
    vy = h // 2 - 80
    for cote, vx in (('L', 15), ('R', w - 135)):
        v = det.vignette(cote)
        if v is None:
            continue
        frame[vy:vy + 160, vx:vx + 120] = v
        cv2.rectangle(frame, (vx - 2, vy - 2), (vx + 122, vy + 162),
                      (0, 165, 255), 2)
    return frame


def draw_zone_centre(frame):
    if not cfg.SHOW_RETICULE or cfg.MODE == "MINIMAL":
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

    # Fleche alerte personne
    if alert_active:
        cv2.arrowedLine(frame, (w-190, cy), (w-30, cy), (0, 0, 255), 8, tipLength=0.4)
        cv2.putText(frame, "PERS", (w-70, cy-30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    # Cible radar la plus proche, au-dela de 50 cm
    if radar_targets:
        dists = [math.hypot(t["x"], t["y"]) for t in radar_targets]
        dists = [d for d in dists if d > 0.5]
        if dists:
            d = min(dists)
            couleur = (0, 0, 255) if d < 2.0 else (0, 165, 255)
            cv2.putText(frame, "RADAR %.1fm" % d, (w-250, cy + 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, couleur, 2)
    return frame


# --------------------------------------------------------------------------------Affichage de la Zone G
def draw_zone_g(frame, text):
    if not text:
        return frame
    h, w = frame.shape[:2]
    x = 200
    y = h - 180
    zone_w = w - 400

    # Fond opaque derriere le texte uniquement
    cv2.rectangle(frame, (x, y - 10), (x + zone_w, h - 10), (0, 0, 0), -1)
    # Texte style sous-titres
    cv2.putText(frame, text[:80], (x + 10, y + 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    return frame


# --------------------------------------------------------------------------------Affichage de la Zone H
def draw_zone_h(frame, temperature, humidity, gas, pressure=0.0):
    h, w = frame.shape[:2]
    x = w - 200
    y = h - 200

    color = (0, 255, 0)
    color_dim = (0, 150, 0)

    # Fond opaque style afficheur
    cv2.rectangle(frame, (x, y), (w-1, h-1), (15, 20, 26), -1)
    cv2.rectangle(frame, (x, y), (w-1, h-1), color_dim, 1)
    cv2.putText(frame, "ENV", (x+90, y+20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 2)

    # Temperature
    cv2.putText(frame, "TEMP :", (x+8, y+60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 2)
    cv2.putText(frame, f"{temperature:.1f}C", (x+65, y+60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

    # Humidite
    cv2.putText(frame, "HUM :", (x+8, y+100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 2)
    cv2.putText(frame, f"{humidity:.0f}%", (x+65, y+100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

    # Gaz VOC : indicateur qualitatif
    if gas > 50000:
        gaz_label, gaz_color = "AIR OK", (0, 255, 0)
    elif gas > 20000:
        gaz_label, gaz_color = "MOYEN", (0, 200, 255)
    else:
        gaz_label, gaz_color = "ALERTE", (0, 0, 255)

    cv2.putText(frame, "GAZ :", (x+8, y+140),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 2)
    cv2.putText(frame, gaz_label, (x+65, y+140),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, gaz_color, 2)

    if cfg.SHOW_GAS_RES:
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

    # Texte centre
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
