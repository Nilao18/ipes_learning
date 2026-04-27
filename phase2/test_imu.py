from adafruit_extended_bus import ExtendedI2C as I2C
from adafruit_bno08x.i2c import BNO08X_I2C
from adafruit_bno08x import BNO_REPORT_ROTATION_VECTOR
import time
import math

def quaternion_to_euler(i, j, k, real):
    roll  = math.atan2(2*(real*i + j*k), 1 - 2*(i*i + j*j))
    pitch = math.asin(max(-1, min(1, 2*(real*j - k*i))))
    yaw   = math.atan2(2*(real*k + i*j), 1 - 2*(j*j + k*k))
    return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)

i2c = I2C(7)
bno = BNO08X_I2C(i2c, address=0x4A)
bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)

while True:
    quat = bno.quaternion
    if quat:
        qi, qj, qk, real = quat
        roll, pitch, yaw = quaternion_to_euler(qi, qj, qk, real)
        print(f"Roll:{roll:7.1f}°  Pitch:{pitch:7.1f}°  Yaw:{yaw:7.1f}°")
    time.sleep(1)
