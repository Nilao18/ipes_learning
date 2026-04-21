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

def detect_motion_zone(prev_gray, gray, seuil=10):
    small_prev = cv2.resize(prev_gray, (160, 90))
    small_gray = cv2.resize(gray, (160, 90))
    diff = cv2.absdiff(small_prev, small_gray)
    _, thresh = cv2.threshold(diff, seuil, 255, cv2.THRESH_BINARY)
    w = thresh.shape[1]
    motion_left  = np.sum(thresh[:, :w//2]) / 255
    motion_right = np.sum(thresh[:, w//2:]) / 255
    return motion_left, motion_right

CAM_LEFT  = "/dev/v4l/by-path/platform-3610000.usb-usb-0:2.1:1.0-video-index0"
CAM_RIGHT = "/dev/v4l/by-path/platform-3610000.usb-usb-0:2.2:1.0-video-index0"

cam_left  = CameraThread(CAM_LEFT)
time.sleep(0.5)
cam_right = CameraThread(CAM_RIGHT)
time.sleep(1)

t0 = time.time()
count = 0
fps = 0
lat_display = 0
lat_update = time.time()

prev_gray_l = None
prev_gray_r = None

alert_l_time = 0
alert_r_time = 0
ALERT_DURATION = 1.5
ZONE_SEUIL = 600

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

    # Flux optique en alternance
    gray_l = cv2.cvtColor(fl, cv2.COLOR_BGR2GRAY)
    gray_r = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
    now_t = time.time()

    if count % 2 == 0:
        if prev_gray_l is not None:
            ml, mr = detect_motion_zone(prev_gray_l, gray_l)
            if ml > ZONE_SEUIL:
                alert_l_time = now_t
            if mr > ZONE_SEUIL:
                alert_r_time = now_t
        prev_gray_l = gray_l.copy()
    else:
        if prev_gray_r is not None:
            ml, mr = detect_motion_zone(prev_gray_r, gray_r)
            if ml > ZONE_SEUIL:
                alert_l_time = now_t
            if mr > ZONE_SEUIL:
                alert_r_time = now_t
        prev_gray_r = gray_r.copy()

    fl = draw_hud(fl, "L", fps, lat_display)
    fr = draw_hud(fr, "R", fps, lat_display)

    # Flèches d'alerte
    h, w = fl.shape[:2]
    if now_t - alert_l_time < ALERT_DURATION:
        cv2.arrowedLine(fl, (200, h//2), (50, h//2), (0,0,255), 8, tipLength=0.4)
        cv2.arrowedLine(fr, (200, h//2), (50, h//2), (0,0,255), 8, tipLength=0.4)
    if now_t - alert_r_time < ALERT_DURATION:
        cv2.arrowedLine(fl, (w-200, h//2), (w-50, h//2), (0,0,255), 8, tipLength=0.4)
        cv2.arrowedLine(fr, (w-200, h//2), (w-50, h//2), (0,0,255), 8, tipLength=0.4)

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
