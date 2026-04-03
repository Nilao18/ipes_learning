import cv2
import numpy as np

# Lire une image depuis le disque
img = cv2.imread("test_image.jpg")
print("Dimensions:", img.shape)
print("Type:", img.dtype)

# Convertir en niveaux de gris
gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
print("Dimensions gris:", gris.shape)

# Filtre gaussien — réduction du bruit
flou = cv2.GaussianBlur(gris, (5, 5), 0)

# Détection de contours Canny
contours = cv2.Canny(flou, 50, 150)

# Sauvegarder les résultats
cv2.imwrite("original.png", img)
cv2.imwrite("gris.png", gris)
cv2.imwrite("flou.png", flou)
cv2.imwrite("contours.png", contours)
print("4 images sauvegardées")
