import cv2
import numpy as np
import time

# Ouvrir la source vidéo
# Sur le Jetson avec caméra USB ce sera : cv2.VideoCapture(0)
# 0 = première caméra, 1 = deuxième, etc.
cap = cv2.VideoCapture("test_video.mp4")

# Vérifier que la source est accessible
if not cap.isOpened():
    print("ERREUR : impossible d'ouvrir la source vidéo")
    exit()

# Infos sur la vidéo
largeur = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
hauteur = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps_source = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

print(f"Résolution : {largeur}x{hauteur}")
print(f"FPS source : {fps_source}")
print(f"Total frames : {total_frames}")

# Créer le writer vidéo
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter('output.mp4', fourcc, fps_source, (largeur, hauteur))

# Boucle de capture
frame_count = 0
temps_debut = time.time()

while True:
    # Lire une frame
    ret, frame = cap.read()

    # ret = False si plus de frames (fin de vidéo)
    if not ret:
        break

    # ── Traitement de la frame ──
    # Convertir en gris
    gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Détection de contours
    flou = cv2.GaussianBlur(gris, (5, 5), 0)
    contours = cv2.Canny(flou, 50, 150)
    
    # Convertir contours (gris) en BGR pour le writer
    contours_bgr = cv2.cvtColor(contours, cv2.COLOR_GRAY2BGR)
    

    # Overlay HUD basique
    cv2.putText(frame, f"Frame: {frame_count}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    frame_count += 1

    # out.write(frame)
    out.write(contours_bgr)
    # Arrêter après 30 frames pour le test
    if frame_count >= 250:
        break

# Libérer la ressource
cap.release()
out.release()
print("Vidéo sauvegardée : output.mp4")
# Calculer le FPS réel de traitement
temps_total = time.time() - temps_debut
fps_reel = frame_count / temps_total

print(f"\nFrames traitées : {frame_count}")
print(f"Temps total : {temps_total:.2f}s")
print(f"FPS réel de traitement : {fps_reel:.1f}")
