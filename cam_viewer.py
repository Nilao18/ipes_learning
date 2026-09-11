#!/usr/bin/env python3
#-----------------------------------------------------------------------------------
# Visionneuse IPES : flux camera en continu sur les lunettes, bascule au clavier SSH,
# indice de nettete pour regler le focus. HUD arrete (une camera = un seul programme).
# Lancement : DISPLAY=:0 python3 cam_viewer.py
#-----------------------------------------------------------------------------------
import os
import sys
import threading
import time

import cv2
import numpy as np

import hud_config as cfg

CAMERAS = [("GAUCHE", cfg.CAM_LEFT), ("DROITE", cfg.CAM_RIGHT),
           ("ARRIERE", cfg.CAM_BACK), ("NUIT IMX462", cfg.CAM_NIGHT)]
AZERTY = {'&': '1', '\u00e9': '2', '"': '3', "'": '4'}   # rangee chiffres sans Maj
touche = None


def lire_clavier():
    """Touches tapees dans le terminal SSH (suivies d'Entree)."""
    global touche
    while True:
        try:
            brut = os.read(sys.stdin.fileno(), 1024)
        except Exception:
            time.sleep(0.1)
            continue
        if not brut:
            time.sleep(0.5)
            continue
        ligne = brut.decode('utf-8', errors='replace').strip()
        if ligne:
            touche = AZERTY.get(ligne[0], ligne[0])


def ouvrir(i):
    """Une seule camera ouverte a la fois : pas de conflit de bande passante sur le hub."""
    nom, chemin = CAMERAS[i]
    cap = cv2.VideoCapture(chemin, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    print(f"Camera {i + 1} : {nom} {'OK' if cap.isOpened() else 'INTROUVABLE'}", flush=True)
    return cap


if __name__ == "__main__":
    threading.Thread(target=lire_clavier, daemon=True).start()
    print("Touches (+ Entree) : n suivante | 1-4 directe | z zoom centre | r raz max | q quitter")
    cv2.namedWindow("IPES CAM", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("IPES CAM", cfg.ECRAN_W, cfg.ECRAN_H)

    # Zone utile du HUD (memes marges que hud_v1)
    hud_w = int(cfg.ECRAN_W * (1 - cfg.MARGE_G - cfg.MARGE_D))
    hud_h = int(cfg.ECRAN_H * (1 - 2 * cfg.MARGE_Y))
    ox, oy = int(cfg.ECRAN_W * cfg.MARGE_G), (cfg.ECRAN_H - hud_h) // 2

    i, zoom = 0, False
    cap = ouvrir(i)
    net, net_max, lum, t_print = 0.0, 0.0, 0.0, 0.0
    vert, orange = (0, 200, 0), (0, 165, 255)

    while True:
        ok, frame = cap.read()
        ecran = np.zeros((cfg.ECRAN_H, cfg.ECRAN_W, 3), np.uint8)
        nom = CAMERAS[i][0]
        if ok:
            frame = cv2.flip(frame, -1)                         # cameras montees a l'envers
            h, w = frame.shape[:2]
            gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            y0, y1, x0, x1 = h // 2 - 150, h // 2 + 150, w // 2 - 200, w // 2 + 200
            net = cv2.Laplacian(gris[y0:y1, x0:x1], cv2.CV_64F).var()   # nettete du centre
            net_max = max(net_max, net)
            lum = gris.mean()
            if zoom:
                vue = frame[y0:y1, x0:x1]
            else:
                vue = frame.copy()
                cv2.rectangle(vue, (x0, y0), (x1, y1), orange, 2)       # zone mesuree
            # Image ajustee dans la zone utile, proportions conservees
            e = min(hud_w / vue.shape[1], hud_h / vue.shape[0])
            vw, vh = int(vue.shape[1] * e), int(vue.shape[0] * e)
            vx, vy = ox + (hud_w - vw) // 2, oy + (hud_h - vh) // 2
            ecran[vy:vy + vh, vx:vx + vw] = cv2.resize(vue, (vw, vh))
        else:
            time.sleep(0.2)                                     # camera absente : pas de boucle a vide
            cv2.putText(ecran, "PAS D'IMAGE", (ox + cfg.COL_G, oy + 200),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, orange, 3)

        # Bandeau : camera, nettete, jauge relative au maximum vu
        tx, ty = ox + cfg.COL_G, oy + 40
        cv2.rectangle(ecran, (tx - 10, ty - 32), (tx + 760, ty + 42), (0, 0, 0), -1)
        cv2.putText(ecran, f"{i + 1} {nom}{'  ZOOM' if zoom else ''}   NETTETE {net:.0f}   MAX {net_max:.0f}"
                    f"   LUM {lum:.0f}", (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.8, vert, 2)
        jauge = int(740 * net / net_max) if net_max > 0 else 0
        cv2.rectangle(ecran, (tx, ty + 15), (tx + 740, ty + 32), (0, 70, 0), 1)
        cv2.rectangle(ecran, (tx, ty + 15), (tx + jauge, ty + 32),
                      vert if jauge > 0.95 * 740 else orange, -1)
        cv2.imshow("IPES CAM", ecran)
        cv2.waitKey(1)

        if time.time() - t_print > 1.0:
            print(f"{nom:12s} nettete {net:7.0f}   max {net_max:7.0f}   lum {lum:5.1f}", flush=True)
            t_print = time.time()

        k, touche = touche, None
        if k == 'q':
            break
        if k == 'n' or k in ('1', '2', '3', '4'):
            j = (i + 1) % len(CAMERAS) if k == 'n' else int(k) - 1
            cap.release()
            time.sleep(0.3)
            i, net_max = j, 0.0
            cap = ouvrir(i)
        elif k == 'z':
            zoom = not zoom
        elif k == 'r':
            net_max = 0.0

    cap.release()
    cv2.destroyAllWindows()
