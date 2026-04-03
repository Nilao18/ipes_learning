import cv2
import numpy as np

# Créer une image synthétique 480x640 (hauteur x largeur) en couleur
img = np.zeros((480, 640, 3), dtype=np.uint8)

# Dessiner des formes — ce sera utile pour les overlays HUD
# Rectangle (coin haut-gauche, coin bas-droit, couleur BGR, épaisseur)
cv2.rectangle(img, (50, 50), (200, 150), (0, 255, 0), 2)

# Cercle (centre, rayon, couleur BGR, épaisseur)
cv2.circle(img, (400, 240), 80, (0, 0, 255), 3)

# Ligne (point1, point2, couleur, épaisseur)
cv2.line(img, (0, 240), (640, 240), (255, 255, 0), 1)

# Texte (texte, position, police, taille, couleur, épaisseur)
cv2.putText(img, "IPES HUD v0.1", (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

# Sauvegarder l'image sur disque
cv2.imwrite("hud_test.png", img)
print("Image sauvegardée : hud_test.png")
print("Dimensions:", img.shape)

# Infos sur l'image
print("Canaux: BGR (pas RGB !)")
print("Bleu pixel [50,50]:", img[50, 50, 0])
print("Vert pixel [50,50]:", img[50, 50, 1])
print("Rouge pixel [50,50]:", img[50, 50, 2])
