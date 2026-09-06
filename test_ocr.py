import cv2
import pytesseract
import numpy as np

# Test sur une image avec du texte
# On va créer une image test avec du texte dessus
img = np.zeros((200, 600, 3), dtype=np.uint8)
img[:] = (50, 50, 50)
cv2.putText(img, "Bonjour IPES test OCR", (10, 100),
            cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 2)

# OCR
config = '--oem 3 --psm 6 -l fra+eng'
text = pytesseract.image_to_string(img, config=config).strip()
print(f"Texte détecté : '{text}'")

# Test sur flux caméra
cap = cv2.VideoCapture('/dev/v4l/by-path/platform-3610000.usb-usb-0:2.1:1.0-video-index0',
                       cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

ret, frame = cap.read()
if ret:
    # Prétraitement pour améliorer l'OCR
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    
    text_cam = pytesseract.image_to_string(gray, config=config).strip()
    print(f"Texte caméra : '{text_cam}'")

cap.release()
print("Test terminé.")
