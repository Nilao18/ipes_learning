import cv2
import time

cap_left = cv2.VideoCapture(0, cv2.CAP_V4L2)
cap_right = cv2.VideoCapture(2, cv2.CAP_V4L2)

for cap in [cap_left, cap_right]:
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)

t0 = time.time()
count = 0

while count < 100:
    ret_l, _ = cap_left.read()
    ret_r, _ = cap_right.read()
    if ret_l and ret_r:
        count += 1
        fps = count / (time.time() - t0)
        print(f"Frame {count}/100 — FPS: {fps:.1f}", end='\r')

print(f"\nFPS moyen sur 100 frames : {fps:.1f}")
cap_left.release()
cap_right.release()
