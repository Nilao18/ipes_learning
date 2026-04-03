import cv2
import numpy as np

# Fond noir — notre "flux caméra"
fond = np.zeros((480, 640, 3), dtype=np.uint8)
cv2.putText(fond, "Flux camera", (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 2)

# Créer un overlay PNG avec transparence (BGRA = 4 canaux)
overlay = np.zeros((480, 640, 4), dtype=np.uint8)

# Rectangle semi-transparent (alpha = 128 = 50% opaque)
cv2.rectangle(overlay, (50, 50), (250, 120), (0, 255, 0, 128), -1)

# Texte pleinement opaque (alpha = 255)
cv2.putText(overlay, "ALTITUDE: 142m", (60, 95),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255, 255), 2)

# Cercle semi-transparent — horizon artificiel
cv2.circle(overlay, (500, 240), 60, (0, 200, 255, 180), 2)
cv2.line(overlay, (440, 240), (560, 240), (0, 200, 255, 180), 1)

# Créer un quadrillage pour meilleure visibilité de la transparence
for c in range(10):
    x = (640 // 10) * c
    y = (480 // 10) * c
    cv2.line(fond, (x, 0), (x, 480), (60, 60, 60), 1)    # ligne verticale
    cv2.line(fond, (0, y), (640, y), (60, 60, 60), 1)    # ligne horizontale

# Alpha blending manuel
alpha = overlay[:, :, 3] / 255.0          # canal alpha normalisé 0.0-1.0
overlay_rgb = overlay[:, :, :3]           # canaux BGR seulement

# Version optimisée — une seule ligne
alpha_3d = alpha[:, :, np.newaxis]  # transforme (480,640) en (480,640,1)
resultat = (overlay_rgb * alpha_3d + fond * (1 - alpha_3d)).astype(np.uint8)

cv2.imwrite("hud_alpha.png", resultat)
print("Sauvegardé : hud_alpha.png")
