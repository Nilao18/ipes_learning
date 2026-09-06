import cv2
import numpy as np

# Paramètres Lucas-Kanade
lk_params = dict(
    winSize=(21, 21),
    maxLevel=3,
    criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
)

# Paramètres détection points d'intérêt (Shi-Tomasi)
feature_params = dict(
    maxCorners=200,
    qualityLevel=0.05,
    minDistance=7,
    blockSize=7
)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 800)

ret, frame = cap.read()
gray_prev = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

# Masque pour exclure zones surexposées
mask_features = np.ones_like(gray_prev)
mask_features[gray_prev > 240] = 0  # exclure pixels trop lumineux
points_prev = cv2.goodFeaturesToTrack(gray_prev, mask=mask_features, **feature_params)

n_frame = 0
print("Flux optique — ENTREE pour capturer, q pour quitter")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray_curr = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    if points_prev is None or len(points_prev) < 10:
        # Redétecter les points si trop peu
        mask_features = np.ones_like(gray_curr)
        mask_features[gray_curr > 240] = 0
        points_prev = cv2.goodFeaturesToTrack(gray_prev, mask=mask_features, **feature_params)
    
    # Calculer le flux optique
    points_curr, status, error = cv2.calcOpticalFlowPyrLK(
        gray_prev, gray_curr, points_prev, None, **lk_params)

    # Garder uniquement les points bien trackés
    if points_curr is not None:
        bons_curr = points_curr[status == 1]
        bons_prev = points_prev[status == 1]

        # Calculer le mouvement moyen
        dx_moyen = np.mean(bons_curr[:, 0] - bons_prev[:, 0])
        dy_moyen = np.mean(bons_curr[:, 1] - bons_prev[:, 1])

        # Dessiner les vecteurs de flux
        display = frame.copy()
        for curr, prev in zip(bons_curr, bons_prev):
            x_curr, y_curr = map(int, curr)
            x_prev, y_prev = map(int, prev)
            # Vecteur de mouvement
            cv2.arrowedLine(display, (x_prev, y_prev), (x_curr, y_curr),
                          (0, 255, 0), 2, tipLength=0.3)
            cv2.circle(display, (x_curr, y_curr), 3, (0, 0, 255), -1)

        # Afficher mouvement global
        cv2.putText(display, f"dx={dx_moyen:.1f}px dy={dy_moyen:.1f}px",
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(display, f"Points trackes: {len(bons_curr)}",
                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        # Alerte mouvement résiduel (simulée sans IMU pour l'instant)
        seuil = 5.0  # pixels
        if abs(dx_moyen) > seuil or abs(dy_moyen) > seuil:
            cv2.putText(display, "MOUVEMENT DETECTE",
                       (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)

        cv2.imwrite(f'/tmp/flux_{n_frame:04d}.jpg', display)
        print(f"Frame {n_frame} — dx={dx_moyen:.1f} dy={dy_moyen:.1f} — {len(bons_curr)} points")

        points_prev = bons_curr.reshape(-1, 1, 2)
    else:
        points_prev = None

    gray_prev = gray_curr.copy()
    n_frame += 1

    cmd = input()
    if cmd == 'q':
        break

cap.release()
print("Terminé.")
