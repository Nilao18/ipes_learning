import cv2
import numpy as np
import glob
import os

# Paramètres du damier
COINS_X = 8  # coins intérieurs horizontaux
COINS_Y = 5  # coins intérieurs verticaux
TAILLE_CASE = 47  # taille d'une case en mm (à mesurer sur ton écran)

# Prépare les points 3D du damier (plan Z=0)
points_3d = np.zeros((COINS_X * COINS_Y, 3), np.float32)
points_3d[:, :2] = np.mgrid[0:COINS_X, 0:COINS_Y].T.reshape(-1, 2)
points_3d *= TAILLE_CASE

objpoints = []  # points 3D
imgpoints = []  # points 2D détectés

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 800)

os.makedirs('/tmp/calib', exist_ok=True)
n_captures = 0
print("Appuie sur ESPACE pour capturer, Q pour calibrer et quitter")
print(f"Objectif : 15-20 captures")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    found, corners = cv2.findChessboardCorners(gray, (COINS_X, COINS_Y), None)

    display = frame.copy()
    if found:
        corners2 = cv2.cornerSubPix(gray, corners, (11,11), (-1,-1),
            (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
        cv2.drawChessboardCorners(display, (COINS_X, COINS_Y), corners2, found)
        cv2.imwrite('/tmp/calib/live.jpg', display)
        print(f"Damier detecte. Appuie sur ENTREE pour capturer, Q+ENTREE pour calibrer ({n_captures}/20)")
    else:
        cv2.imwrite('/tmp/calib/live.jpg', display)
        print("Damier non detecte...")

    cmd = input()
    if cmd == '' and found:
        objpoints.append(points_3d)
        imgpoints.append(corners2)
        cv2.imwrite(f'/tmp/calib/capture_{n_captures:02d}.jpg', frame)
        n_captures += 1
        print(f"Capture {n_captures} OK")
    elif cmd == 'q' and n_captures >= 10:
        break

cap.release()

if n_captures < 10:
    print("Pas assez de captures")
else:
    print(f"\nCalibration avec {n_captures} images...")
    ret, K, dist, rvecs, tvecs = cv2.calibrateCamera(
        objpoints, imgpoints, gray.shape[::-1], None, None)
    
    print(f"\nMatrice K :\n{K}")
    print(f"\nDistorsion : {dist}")
    print(f"\nErreur de reprojection : {ret:.4f} pixels")
    
    np.save('/tmp/calib/K.npy', K)
    np.save('/tmp/calib/dist.npy', dist)
    print("\nK et dist sauvegardés dans /tmp/calib/")
