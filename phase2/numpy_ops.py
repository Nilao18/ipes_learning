import numpy as np

# Simuler une petite image en niveaux de gris
img = np.array([
    [10,  50,  200, 30],
    [80,  120, 90,  255],
    [0,   45,  170, 60],
    [230, 15,  100, 5]
], dtype=np.uint8)

print("Image originale:")
print(img)
print()

# Statistiques utiles pour analyser une image
print("Valeur min:", img.min())
print("Valeur max:", img.max())
print("Moyenne:", img.mean())
print()

# Seuillage — pixels > 100 deviennent 255, les autres 0
seuil = np.where(img > 100, 255, 0)
print("Après seuillage (> 100):")
print(seuil)
print()

# Découper une région d'intérêt (ROI)
# Lignes 1 à 3, colonnes 1 à 3
roi = img[1:3, 1:3]
print("Région d'intérêt [1:3, 1:3]:")
print(roi)
