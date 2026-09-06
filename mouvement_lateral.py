import cv2
import numpy as np
import time

CAM_LEFT = "/dev/v4l/by-path/platform-3610000.usb-usb-0:2.1:1.0-video-index0"

cap = cv2.VideoCapture(CAM_LEFT, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_FPS, 30)

ret, prev = cap.read()
prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)

SEUIL = 3.0  # pixels de mouvement moyen

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Points à tracker
    pts = cv2.goodFeaturesToTrack(prev_gray, maxCorners=100,
                                   qualityLevel=0.3, minDistance=7)

    if pts is not None:
        # Flux optique Lucas-Kanade
        pts_new, status, _ = cv2.calcOpticalFlowPyrLK(
            prev_gray, gray, pts, None)

        # Garder uniquement les points bien trackés
        good_old = pts[status == 1]
        good_new = pts_new[status == 1]

        # Vecteur mouvement moyen horizontal
        if len(good_new) > 0:
            dx = np.mean(good_new[:, 0] - good_old[:, 0])
            dy = np.mean(good_new[:, 1] - good_old[:, 1])

            # Affichage
            if abs(dx) > SEUIL:
                direction = ">>> DROITE >>>" if dx > 0 else "<<< GAUCHE <<<"
                print(f"{direction}  dx={dx:.1f}px  dy={dy:.1f}px")
            else:
                print(f"stable  dx={dx:.1f}px", end='\r')

    prev_gray = gray.copy()

cap.release()
