import cv2
import numpy as np

# Charger les paramètres de calibration
K = np.load('/tmp/calib/K.npy')
dist = np.load('/tmp/calib/dist.npy')

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 800)

ret, frame = cap.read()
cap.release()

# Corriger la distorsion
frame_corrige = cv2.undistort(frame, K, dist)

# Sauvegarder les deux
cv2.imwrite('/tmp/calib/original.jpg', frame)
cv2.imwrite('/tmp/calib/corrige.jpg', frame_corrige)
print("Images sauvegardées.")
