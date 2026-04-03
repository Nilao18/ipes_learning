import numpy as np

# Une image en niveaux de gris = tableau 2D
# 4 pixels de haut, 6 pixels de large
image = np.zeros((4, 6), dtype=np.uint8)
print("Image vide (noirs):")
print(image)
print("Forme:", image.shape)
print("Type:", image.dtype)

# Allumer quelques pixels
image[0, 0] = 255   # pixel en haut à gauche = blanc
image[2, 3] = 128   # pixel au milieu = gris
print("\nImage modifiée:")
print(image)

# Une image couleur RGB = tableau 3D (hauteur, largeur, canaux)
image_rgb = np.zeros((4, 6, 3), dtype=np.uint8)
image_rgb[0, 0] = [255, 0, 0]   # rouge pur en haut à gauche
print("\nImage RGB - pixel [0,0]:", image_rgb[0, 0])
print("Forme RGB:", image_rgb.shape)
