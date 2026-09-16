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
    if cfg.actif("boussole"):
        cv2.rectangle(overlay,
                      (cx - compass_w//2 - 5, 0),
                      (cx + compass_w//2 + 5, 95),
                      (0, 0, 0), -1)
    if cfg.actif("altimetre"):
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
    if cfg.actif("horizon"):
        frame = draw_horizon(frame, roll, pitch)

    # Boussole
    COMPASS_OFFSET = -45
    if cfg.actif("boussole"):
        frame = draw_compass(frame, (-yaw + COMPASS_OFFSET) % 360)

    # Altitude barometrique
    alt_m = 44330 * (1 - (pressure / 1013.25) ** 0.1903)
    alt_ft = alt_m * 3.28084

    color_large = (255, 255, 255)
    color_small = (0, 200, 0)
    color_dim = (0, 150, 0)

    compass_left  = cx - compass_w//2 - 10
    compass_right = cx + compass_w//2 + 10

    if cfg.actif("altimetre"):
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
def draw_zone_c(frame, fps, side="", jetson_temp=0, cpu=0, lat=0, gps=None, radar=None,
                casque=None, cams_hs=()):
    """Donnees systeme (Zone A) : lignes empilees, une ligne masquee ne laisse pas de trou."""
    x, y = cfg.COL_G, 10
    color_dim = (0, 150, 0)
    now = datetime.now()

    # (texte, echelle, couleur, ecart avec la ligne precedente)
    lignes = [(now.strftime("%H:%M:%S"), 0.8, color_dim, 20)]
    if cfg.actif("systeme_detail"):
        temp_color = (0, 0, 255) if jetson_temp > 75 else color_dim
        lignes += [(now.strftime("%d/%m/%Y"), 0.6, color_dim, 25),
                   (f"CPU:{cpu:.0f}%", 0.6, color_dim, 25),
                   (f"T:{jetson_temp:.0f}C", 0.6, temp_color, 25)]
        if gps is not None and not gps.connecte:
            lignes.append(("GPS HS", 0.6, (0, 165, 255), 30))
        elif gps is not None:
            # Deux lignes courtes : la zone B dessine ensuite un fond noir a partir
            # de x=293, qui tronquait l'ancien libelle "GPS HDOP x.x"
            if gps.fix:
                gps_color = (0, 165, 255) if gps.hdop > 5 else color_dim
                l1 = f"GPS {gps.satellites} SAT"
                l2 = f"HDOP {gps.hdop:.1f}"
            else:
                gps_color = (0, 165, 255)
                l1 = "GPS NO FIX"
                l2 = f"{gps.satellites} SAT"
            lignes += [(l1, 0.6, gps_color, 30),
                       (l2, 0.6, gps_color, 25)]
    lignes.append((cfg.MODE, 0.7, (0, 200, 255), 30))
    if not cfg.actif("radar"):
        lignes.append(("RADAR OFF", 0.6, (100, 100, 100), 30))
    elif radar is not None and not radar.connecte:
        lignes.append(("RADAR HS", 0.6, (0, 165, 255), 30))
    if casque is not None and not casque.imu_ok:
        lignes.append(("CASQUE HS", 0.6, (0, 165, 255), 30))
    if cams_hs:
        # Une camera debranchee est sautee en silence par la rotation de detection :
        # sans cet indicateur, la panne ne se voit qu'au manque d'alertes d'un cote.
        lignes.append(("CAM %s HS" % " ".join(cams_hs), 0.6, (0, 165, 255), 30))
    if cfg.DEBUG:
        lignes += [(f"FPS:{fps:.1f}", 0.6, color_dim, 30),
                   (f"LAT:{lat:.0f}ms", 0.6, color_dim, 20),
                   (side, 0.6, color_dim, 20)]

    for texte, echelle, couleur, ecart in lignes:
        y += ecart
        cv2.putText(frame, texte, (x, y), cv2.FONT_HERSHEY_SIMPLEX, echelle, couleur, 2)
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


def draw_sentinelle(frame, radar_targets=None, alerte_g=False, alerte_d=False, det=None,
                    alerte_a=False):
    """Cadran vue de dessus : toi au centre, avant en haut. Angle 0 = avant, positif = droite."""
    h, w = frame.shape[:2]
    R = cfg.SENTINELLE_R
    cx, cy = w // 2, h - R - 20
    pm = R / cfg.SENTINELLE_PORTEE                     # pixels par metre
    vert, gris, orange = (0, 150, 0), (90, 90, 90), (0, 165, 255)

    def point(angle, dist):
        a = math.radians(angle)
        r = min(dist, cfg.SENTINELLE_PORTEE) * pm
        return int(cx + r * math.sin(a)), int(cy - r * math.cos(a))

    def arc(centre, ouverture, couleur):
        # angles OpenCV : 0 = droite, sens horaire -> angle cadran - 90
        cv2.ellipse(frame, (cx, cy), (R, R), 0, centre - ouverture / 2 - 90,
                    centre + ouverture / 2 - 90, couleur, 4)

    # Anneaux tous les 2 m et contour
    for d in range(2, int(cfg.SENTINELLE_PORTEE), 2):
        cv2.circle(frame, (cx, cy), int(d * pm), (0, 70, 0), 1)
    cv2.circle(frame, (cx, cy), R, (0, 90, 0), 1)

    # Couverture capteurs sur le contour (absence d'arc = angle mort)
    arc(0, cfg.RADAR_FOV, vert if cfg.actif("radar") else gris)
    arc(-90, cfg.CAM_HFOV, orange if alerte_g else vert)
    arc(90, cfg.CAM_HFOV, orange if alerte_d else vert)
    arc(180, cfg.CAM_HFOV, orange if alerte_a else vert)

    # Toi : triangle pointe vers l'avant
    pts = np.array([(cx, cy - 10), (cx - 7, cy + 7), (cx + 7, cy + 7)], np.int32)
    cv2.fillPoly(frame, [pts], (255, 255, 255))

    # Cibles radar : x negatif = droite du radar (valide en test)
    if cfg.actif("radar") and radar_targets:
        for t in radar_targets:
            dist = math.hypot(t["x"], t["y"])
            if dist <= 0.5:
                continue
            px, py = point(math.degrees(math.atan2(-t["x"], t["y"])), dist)
            couleur = (0, 0, 255) if dist < 2.0 else orange
            cv2.circle(frame, (px, py), 6, couleur, -1)
            txt = "%.1fm" % dist
            (tw, _), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.putText(frame, txt, (px - tw // 2, py + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, couleur, 1)

    # Personnes vues par les cameras laterales : carres creux (position estimee)
    # Direction : image redressee, a droite de l'image = vers l'avant pour la camera gauche,
    # vers l'arriere pour la droite. Distance : taille apparente d'une personne debout.
    if det is not None:
        for cote, axe in (("L", -90.0), ("R", 90.0), ("B", 180.0)):
            for (x, y, bw, bh, _) in det.personnes(cote):
                angle = axe + math.degrees(math.atan((x + bw / 2 - cfg.CAM_W / 2) / cfg.CAM_FX))
                dist = cfg.CAM_FX * cfg.TAILLE_PERSONNE / max(bh, 1)
                coupee = (y <= 2 or y + bh >= cfg.CAM_H - 2          # coupee par le bord
                          or bh < cfg.RATIO_ENTIER * bw)        # ou masquee : plus proche qu'estime
                px, py = point(angle, dist)
                couleur = (0, 0, 255) if dist < 2.0 else orange
                cv2.rectangle(frame, (px - 6, py - 6), (px + 6, py + 6), couleur, 2)
                txt = ("<" if coupee else "~") + ("%.1fm" % dist if dist < 2.0 else "%.0fm" % dist)
                (tw, _), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                cv2.putText(frame, txt, (px - tw // 2, py + 22),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, couleur, 1)
    return frame


def draw_menu(frame, niveau, index, mode_edite, couches_edit, verrous):
    """Menu de reglages au centre du champ. niveau 0 = choix du mode, 1 = ses couches."""
    h, w = frame.shape[:2]
    if niveau == 0:
        titre = "REGLAGES - choisir un mode"
        items = [(m, None) for m in cfg.MODES_EDITABLES]
    else:
        titre = "REGLAGES - %s" % mode_edite
        items = [(cfg.LIBELLES.get(c, c), c) for c in cfg.COUCHES]
        items += [("VALIDER", "_ok"), ("RETOUR", "_retour")]

    pw, ligne_h = 520, 30
    ph = 100 + len(items) * ligne_h
    x, y = (w - pw) // 2, (h - ph) // 2
    cv2.rectangle(frame, (x, y), (x + pw, y + ph), (10, 14, 18), -1)
    cv2.rectangle(frame, (x, y), (x + pw, y + ph), (0, 200, 255), 2)
    cv2.putText(frame, titre, (x + 20, y + 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
    cv2.line(frame, (x + 10, y + 50), (x + pw - 10, y + 50), (0, 90, 0), 1)

    for i, (libelle, cle) in enumerate(items):
        ly = y + 78 + i * ligne_h
        verrou = cle in verrous
        if verrou:
            couleur = (110, 110, 110)          # grise : imposee par le mode
        elif cle in ("_ok", "_retour"):
            couleur = (0, 200, 255)
        else:
            couleur = (0, 255, 0) if cle in couches_edit else (0, 110, 0)

        if i == index:                          # ligne selectionnee
            cv2.rectangle(frame, (x + 8, ly - 20), (x + pw - 8, ly + 8), (0, 60, 90), -1)
            cv2.putText(frame, ">", (x + 14, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (0, 200, 255), 2)
        if niveau == 1 and cle not in ("_ok", "_retour"):
            coche = "[X]" if (cle in couches_edit or verrou) else "[ ]"
            cv2.putText(frame, coche, (x + 40, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.6, couleur, 2)
            cv2.putText(frame, libelle, (x + 100, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.6, couleur, 2)
        else:
            cv2.putText(frame, libelle, (x + 40, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.6, couleur, 2)

    aide = "encodeur : deplacer   |   poussoir encodeur : valider"
    cv2.putText(frame, aide, (x + 20, y + ph - 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 150, 0), 1)
    return frame


_bande_cache = {}


def _bande_danger(h, w):
    """Motif rayures diagonales orange/noir (le noir est transparent dans les Xreal)."""
    if (h, w) not in _bande_cache:
        yy, xx = np.mgrid[0:h, 0:w]
        motif = np.zeros((h, w, 3), dtype=np.uint8)
        motif[((xx + yy) // cfg.ALERT_STRIPE) % 2 == 0] = (0, 165, 255)
        _bande_cache[(h, w)] = motif
    return _bande_cache[(h, w)]


def draw_alert_bars(ecran, ox, oy, hud_w, hud_h, gauche, droite, bas=False):
    """Bandes d'alerte : a gauche au debut de la zone nette, a droite hors zone utile,
    en bas (arriere) entre les deux bandes laterales."""
    bw, gap = cfg.ALERT_BAR_W, cfg.ALERT_BAR_GAP
    motif = _bande_danger(hud_h, bw)
    if gauche:
        x = ox + cfg.NET_G
        ecran[oy:oy + hud_h, x:x + bw] = motif
    if droite:
        x = ox + hud_w + gap
        ecran[oy:oy + hud_h, x:x + bw] = motif
    if bas:
        x0, x1 = ox + cfg.NET_G, ox + hud_w + gap + bw
        y = oy + hud_h + gap if cfg.ALERT_BAS_MARGE else oy + hud_h - bw
        ecran[y:y + bw, x0:x1] = _bande_danger(bw, x1 - x0)
    return ecran


def draw_vignettes(frame, det):
    """Imagettes des personnes detectees, cote correspondant."""
    h, w = frame.shape[:2]
    vy = h // 2 - 80
    for cote, vx in (('L', cfg.COL_G), ('R', w - 135)):
        v = det.vignette(cote)
        if v is None:
            continue
        frame[vy:vy + 160, vx:vx + 120] = v
        cv2.rectangle(frame, (vx - 2, vy - 2), (vx + 122, vy + 162),
                      (0, 165, 255), 2)
        txt = f"{det.compte(cote)} PERS"
        (tw, _), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.putText(frame, txt, (vx + (120 - tw) // 2, vy + 190),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

    # Arriere : retroviseur en haut au centre, image en miroir (gauche = ta gauche)
    v = det.vignette('B')
    if v is not None:
        vx, vy = w // 2 - 60, cfg.RETRO_Y
        frame[vy:vy + 160, vx:vx + 120] = cv2.flip(v, 1)
        cv2.rectangle(frame, (vx - 2, vy - 2), (vx + 122, vy + 162),
                      (0, 165, 255), 2)
        txt = f"ARR {det.compte('B')} PERS"
        (tw, _), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.putText(frame, txt, (vx + (120 - tw) // 2, vy + 190),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
    return frame


def draw_zone_centre(frame):
    if not cfg.actif("reticule"):
        return frame
    h, w = frame.shape[:2]
    cx, cy = w//2, h//2
    color = (0, 255, 0)
    cv2.line(frame, (cx-20, cy), (cx+20, cy), color, 2)
    cv2.line(frame, (cx, cy-20), (cx, cy+20), color, 2)
    cv2.circle(frame, (cx, cy), 30, color, 2)
    return frame


# --------------------------------------------------------------------------------Affichage de la Zone E
def draw_zone_e(frame, radar_targets=None):
    h, w = frame.shape[:2]
    cy = h // 2

    # Cible radar la plus proche, au-dela de 50 cm
    # Le cadran affiche deja la distance : pas de doublon en texte
    if cfg.actif("radar") and radar_targets and not cfg.actif("cadran"):
        dists = [math.hypot(t["x"], t["y"]) for t in radar_targets]
        dists = [d for d in dists if d > 0.5]
        if dists:
            d = min(dists)
            couleur = (0, 0, 255) if d < 2.0 else (0, 165, 255)
            cv2.putText(frame, "RADAR %.1fm" % d, (w-250, cy + 140),
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
    txt = text if len(text) <= 80 else text[:77] + "..."
    cv2.putText(frame, txt, (x + 10, y + 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    return frame


# --------------------------------------------------------------------------------Affichage de la Zone H
def _valeur(frame, txt, x, y, couleur, largeur_max):
    """Ecrit une valeur en reduisant la police jusqu'a tenir dans le cadre."""
    for echelle in (0.8, 0.7, 0.6, 0.5, 0.45):
        (tw, _), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, echelle, 2)
        if tw <= largeur_max:
            break
    cv2.putText(frame, txt, (x, y), cv2.FONT_HERSHEY_SIMPLEX, echelle, couleur, 2)


def draw_zone_h(frame, temperature, humidity, gas, pressure=0.0, chauffe=0):
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
    _valeur(frame, f"{temperature:.1f}C", x+65, y+60, color, w - 9 - (x+65))

    # Humidite
    cv2.putText(frame, "HUM :", (x+8, y+100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 2)
    _valeur(frame, f"{humidity:.0f}%", x+65, y+100, color, w - 9 - (x+65))

    # Gaz VOC : indicateur qualitatif, precede du decompte de chauffe
    if chauffe > 0:
        gaz_label, gaz_color = "CHAUFFE %ds" % int(chauffe), (0, 165, 255)
    elif gas > 50000:
        gaz_label, gaz_color = "AIR OK", (0, 255, 0)
    elif gas > 20000:
        gaz_label, gaz_color = "MOYEN", (0, 200, 255)
    else:
        gaz_label, gaz_color = "ALERTE", (0, 0, 255)

    cv2.putText(frame, "GAZ :", (x+8, y+140),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 2)
    _valeur(frame, gaz_label, x+65, y+140, gaz_color, w - 9 - (x+65))

    if cfg.SHOW_GAS_RES:
        cv2.putText(frame, f"Gas res :{gas//1000}k ohm", (x+8, y+160),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_dim, 1)

    # Pression
    cv2.putText(frame, "PRES :", (x+8, y+180),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 2)
    _valeur(frame, f"{pressure:.0f}hPa", x+65, y+180, color, w - 9 - (x+65))
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
