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
        self.running = True
        self.thread = threading.Thread(target=self.update)
        self.thread.daemon = True
        self.thread.start()

    def update(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                self.frame = frame

    def stop(self):
        self.running = False
        self.cap.release()

def draw_hud(frame, side, fps):
    h, w = frame.shape[:2]
    now = datetime.now()
    color = (0, 255, 0)
    cv2.putText(frame, now.strftime("%H:%M:%S"), (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    cv2.putText(frame, now.strftime("%d/%m/%Y"), (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)
    cv2.putText(frame, f"FPS:{fps:.1f}", (10, 90),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)
    cv2.putText(frame, side, (w-80, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    cx, cy = w//2, h//2
    cv2.line(frame, (cx-20, cy), (cx+20, cy), color, 1)
    cv2.line(frame, (cx, cy-20), (cx, cy+20), color, 1)
    cv2.circle(frame, (cx, cy), 30, color, 1)
    return frame

cam_left = CameraThread(0)
cam_right = CameraThread(2)
time.sleep(1)

t0 = time.time()
count = 0
fps = 0

while count < 200:
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

    fl = draw_hud(fl, "L", fps)
    fr = draw_hud(fr, "R", fps)

    composite = np.hstack([fl, fr])

    count += 1
    fps = count / (time.time() - t0)
    print(f"Frame {count}/200 — FPS: {fps:.1f}", end='\r')

print(f"\nFPS pipeline complet : {fps:.1f}")
cam_left.stop()
cam_right.stop()
