import cv2
import numpy as np

# Charger paramètres stéréo
K_g = np.load('/home/quentin/ipes/calibration/K_ov9281_gauche.npy')
dist_g = np.load('/home/quentin/ipes/calibration/dist_ov9281_gauche.npy')
K_d = np.load('/home/quentin/ipes/calibration/K_ov9281_droite.npy')
dist_d = np.load('/home/quentin/ipes/calibration/dist_ov9281_droite.npy')
R = np.load('/home/quentin/ipes/calibration/R.npy')
T = np.load('/home/quentin/ipes/calibration/T.npy')
R1 = np.load('/home/quentin/ipes/calibration/R1.npy')
R2 = np.load('/home/quentin/ipes/calibration/R2.npy')
P1 = np.load('/home/quentin/ipes/calibration/P1.npy')
P2 = np.load('/home/quentin/ipes/calibration/P2.npy')
Q = np.load('/home/quentin/ipes/calibration/Q.npy')

# Calculer les maps de rectification
img_size = (1280, 800)
map1_g, map2_g = cv2.initUndistortRectifyMap(K_g, dist_g, R1, P1, img_size, cv2.CV_32FC1)
map1_d, map2_d = cv2.initUndistortRectifyMap(K_d, dist_d, R2, P2, img_size, cv2.CV_32FC1)

# Caméras
cap_g = cv2.VideoCapture(0)
cap_d = cv2.VideoCapture(2)
for cap in [cap_g, cap_d]:
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 800)

# SGBM — paramètres
window_size = 5
sgbm = cv2.StereoSGBM_create(
    minDisparity=0,
    numDisparities=128,
    blockSize=window_size,
    P1=8 * 3 * window_size**2,
    P2=32 * 3 * window_size**2,
    disp12MaxDiff=1,
    uniquenessRatio=10,
    speckleWindowSize=100,
    speckleRange=32,
    preFilterCap=63,
    mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
)

print("Capture en cours... ENTREE pour capturer, q pour quitter")

while True:
    ret_g, frame_g = cap_g.read()
    ret_d, frame_d = cap_d.read()
    if not ret_g or not ret_d:
        break

    # Rectifier
    rect_g = cv2.remap(frame_g, map1_g, map2_g, cv2.INTER_LINEAR)
    rect_d = cv2.remap(frame_d, map1_d, map2_d, cv2.INTER_LINEAR)

    # Convertir en gris
    gray_g = cv2.cvtColor(rect_g, cv2.COLOR_BGR2GRAY)
    gray_d = cv2.cvtColor(rect_d, cv2.COLOR_BGR2GRAY)

    # Calculer disparité
    disparity = sgbm.compute(gray_g, gray_d).astype(np.float32) / 16.0

    # Normaliser pour visualisation
    disp_vis = cv2.normalize(disparity, None, 0, 255, cv2.NORM_MINMAX)
    disp_vis = np.uint8(disp_vis)
    disp_color = cv2.applyColorMap(disp_vis, cv2.COLORMAP_JET)

    # Calculer distance au centre
    cx, cy = 640, 400
    d = disparity[cy, cx]
    if d > 0:
        baseline = 66.39  # mm
        fx = P1[0, 0]
        Z = (fx * baseline) / d / 1000  # en mètres
        texte = f"Distance centre: {Z:.2f}m"
    else:
        texte = "Distance centre: N/A"

    cv2.putText(disp_color, texte, (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    # Sauvegarder
    cv2.imwrite('/tmp/disparite.jpg', disp_color)
    cv2.imwrite('/tmp/rect_g.jpg', rect_g)
    cv2.imwrite('/tmp/rect_d.jpg', rect_d)
    print(texte)

    cmd = input()
    if cmd == 'q':
        break

cap_g.release()
cap_d.release()
print("Terminé.")
