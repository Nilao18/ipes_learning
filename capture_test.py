import cv2

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 800)

ret, frame = cap.read()
if ret:
    cv2.imwrite('/tmp/capture_python.jpg', frame)
    print(f"Image capturée : {frame.shape}")
else:
    print("Erreur de capture")

cap.release()
