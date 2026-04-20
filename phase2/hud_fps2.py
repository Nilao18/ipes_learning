import cv2
import time
import threading

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

cam_left = CameraThread(0)
cam_right = CameraThread(2)

time.sleep(1)  # laisser les threads démarrer

t0 = time.time()
count = 0

while count < 100:
    if cam_left.frame is not None and cam_right.frame is not None:
        count += 1
        fps = count / (time.time() - t0)
        print(f"Frame {count}/100 — FPS: {fps:.1f}", end='\r')

print(f"\nFPS moyen sur 100 frames : {fps:.1f}")
cam_left.stop()
cam_right.stop()
