import cv2
import numpy as np
import os

COINS_X = 8
COINS_Y = 5
TAILLE_CASE = 48  # mm

points_3d = np.zeros((COINS_X * COINS_Y, 3), np.float32)
points_3d[:, :2] = np.mgrid[0:COINS_X, 0:COINS_Y].T.reshape(-1, 2)
points_3d *= TAILLE_CASE

# Charger calibrations individuelles
K_g = np.load('/home/quentin/ipes/calibration/K_ov9281_gauche.npy')
dist_g = np.load('/home/quentin/ipes/calibration/dist_ov9281_gauche.npy')
K_d = np.load('/home/quentin/ipes/calibration/K_ov9281_droite.npy')
dist_d = np.load('/home/quentin/ipes/calibration/dist_ov9281_droite.npy')

objpoints = []
imgpoints_g = []
imgpoints_d = []

cap_g = cv2.VideoCapture(0)
cap_d = cv2.VideoCapture(2)
for cap in [cap_g, cap_d]:
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 800)

n_captures = 0
print("Calibration stéréo — positionne le damier visible par LES DEUX caméras")
print("ENTREE = capturer, q = calibrer et quitter (min 15 captures)")

while True:
    ret_g, frame_g = cap_g.read()
    ret_d, frame_d = cap_d.read()
    if not ret_g or not ret_d:
        break

    gray_g = cv2.cvtColor(frame_g, cv2.COLOR_BGR2GRAY)
    gray_d = cv2.cvtColor(frame_d, cv2.COLOR_BGR2GRAY)

    found_g, corners_g = cv2.findChessboardCorners(gray_g, (COINS_X, COINS_Y), None)
    found_d, corners_d = cv2.findChessboardCorners(gray_d, (COINS_X, COINS_Y), None)

    if found_g and found_d:
        print(f"DAMIER DETECTE dans les deux cameras ({n_captures}/15) — ENTREE pour capturer")
    else:
        statut_g = "OK" if found_g else "NON"
        statut_d = "OK" if found_d else "NON"
        print(f"Gauche: {statut_g}  Droite: {statut_d} — repositionne le damier")

    # Sauvegarder aperçu
    cv2.imwrite('/tmp/calib/stereo_g.jpg', frame_g)
    cv2.imwrite('/tmp/calib/stereo_d.jpg', frame_d)

    cmd = input()
    if cmd == '' and found_g and found_d:
        corners2_g = cv2.cornerSubPix(gray_g, corners_g, (11,11), (-1,-1),
            (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
        corners2_d = cv2.cornerSubPix(gray_d, corners_d, (11,11), (-1,-1),
            (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
        objpoints.append(points_3d)
        imgpoints_g.append(corners2_g)
        imgpoints_d.append(corners2_d)
        n_captures += 1
        print(f"Capture {n_captures} OK")
    elif cmd == 'q' and n_captures >= 15:
        break

cap_g.release()
cap_d.release()

print(f"\nCalibration stéréo avec {n_captures} images...")
img_size = (1280, 800)

ret, K_g, dist_g, K_d, dist_d, R, T, E, F = cv2.stereoCalibrate(
    objpoints, imgpoints_g, imgpoints_d,
    K_g, dist_g, K_d, dist_d,
    img_size,
    flags=cv2.CALIB_FIX_INTRINSIC
)

print(f"\nErreur de reprojection stéréo : {ret:.4f} pixels")
print(f"\nRotation R :\n{R}")
print(f"\nTranslation T (mm) :\n{T}")
print(f"\nBaseline mesurée : {np.linalg.norm(T):.2f} mm")

# Rectification
R1, R2, P1, P2, Q, roi1, roi2 = cv2.stereoRectify(
    K_g, dist_g, K_d, dist_d, img_size, R, T)

# Sauvegarder tout
np.save('/home/quentin/ipes/calibration/R.npy', R)
np.save('/home/quentin/ipes/calibration/T.npy', T)
np.save('/home/quentin/ipes/calibration/R1.npy', R1)
np.save('/home/quentin/ipes/calibration/R2.npy', R2)
np.save('/home/quentin/ipes/calibration/P1.npy', P1)
np.save('/home/quentin/ipes/calibration/P2.npy', P2)
np.save('/home/quentin/ipes/calibration/Q.npy', Q)
print("\nParamètres stéréo sauvegardés.")
