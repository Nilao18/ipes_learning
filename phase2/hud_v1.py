import cv2
import numpy as np
import threading
import time
from datetime import datetime

class CameraThread:
    def __init__(self, device):
        self.cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.frame = None
        self.timestamp = None
        self.running = True
        self.thread = threading.Thread(target=self.update)
        self.thread.daemon = True
        self.thread.start()

    def update(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                self.frame = frame
                self.timestamp = time.time()

    def stop(self):
        self.running = False
        self.cap.release()

def draw_hud(frame, side, fps, lat):
    h, w = frame.shape[:2]
    now = datetime.now()
    color = (0, 255, 0)
    cv2.putText(frame, now.strftime("%H:%M:%S"), (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    cv2.putText(frame, now.strftime("%d/%m/%Y"), (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)
    cv2.putText(frame, f"FPS:{fps:.1f}", (10, 90),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)
    cv2.putText(frame, f"LAT:{lat:.0f}ms", (10, 120),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)
    cv2.putText(frame, side, (w-80, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    cx, cy = w//2, h//2
    cv2.line(frame, (cx-20, cy), (cx+20, cy), color, 1)
    cv2.line(frame, (cx, cy-20), (cx, cy+20), color, 1)
    cv2.circle(frame, (cx, cy), 30, color, 1)
    return frame

CAM_LEFT  = "/dev/v4l/by-path/platform-3610000.usb-usb-0:2.1:1.0-video-index0"
CAM_RIGHT = "/dev/v4l/by-path/platform-3610000.usb-usb-0:2.2:1.0-video-index0"


cam_left  = CameraThread(CAM_LEFT)
time.sleep(0.5)
cam_right = CameraThread(CAM_RIGHT)
time.sleep(0.5)

t0 = time.time()
count = 0
fps = 0
lat_display = 0
lat_update = time.time()

cv2.namedWindow("IPES HUD V1", cv2.WINDOW_NORMAL)
cv2.setWindowProperty("IPES HUD V1", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
cv2.resizeWindow("IPES HUD V1", 1440, 2880)

while True:
    if cam_left.frame is None or cam_right.frame is None:
        continue

    fl = cam_left.frame.copy()
    fr = cam_right.frame.copy()

    if len(fl.shape) == 2:
        fl = cv2.cvtColor(fl, cv2.COLOR_GRAY2BGR)
    if len(fr.shape) == 2:
        fr = cv2.cvtColor(fr, cv2.COLOR_GRAY2BGR)

    fl = cv2.resize(fl, (1440, 1440))
    fr = cv2.resize(fr, (1440, 1440))

    if time.time() - lat_update > 1.0:
        lat_display = (time.time() - cam_left.timestamp) * 1000
        lat_update = time.time()

    fl = draw_hud(fl, "L", fps, lat_display)
    fr = draw_hud(fr, "R", fps, lat_display)

    composite = np.vstack([fl, fr])

    count += 1
    fps = count / (time.time() - t0)

    cv2.imshow("IPES HUD V1", composite)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

print(f"\nFPS pipeline complet : {fps:.1f}")
cam_left.stop()
cam_right.stop()
cv2.destroyAllWindows()
