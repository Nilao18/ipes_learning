from onnxtr.io import DocumentFile
from onnxtr.models import ocr_predictor
import cv2
import time

model = ocr_predictor(
    det_arch="db_mobilenet_v3_large",
    reco_arch="crnn_mobilenet_v3_small"
)

cap = cv2.VideoCapture('/dev/v4l/by-path/platform-3610000.usb-usb-0:2.1:1.0-video-index0', cv2.CAP_V4L2)
ret, frame = cap.read()
cap.release()

if ret:
    cv2.imwrite('/tmp/cam_frame.png', frame)
    doc = DocumentFile.from_images('/tmp/cam_frame.png')
    
    t0 = time.time()
    result = model(doc)
    dt = time.time() - t0
    
    print(f"Temps inférence : {dt*1000:.0f}ms")
    print(result.render())
