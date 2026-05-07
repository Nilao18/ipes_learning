import serial
import struct
import time

s = serial.Serial('/dev/ttyUSB0', 256000, timeout=1)

def parse_frame(data):
    start = -1
    for i in range(len(data) - 1):
        if data[i] == 0xAA and data[i+1] == 0xFF:
            start = i
            break
    if start == -1:
        return None

    end = -1
    for i in range(start, len(data) - 1):
        if data[i] == 0x55 and data[i+1] == 0xCC:
            end = i + 2
            break
    if end == -1:
        return None

    frame = data[start:end]
    if len(frame) < 30:
        return None

    def decode_coord(raw):
        sign = -1 if (raw & 0x8000) else 1
        value = raw & 0x7FFF
        return sign * value / 100.0

    targets = []
    for t in range(3):
        offset = 4 + t * 8
        if offset + 8 > len(frame):
            break
        x_raw = struct.unpack_from('<H', frame, offset)[0]
        y_raw = struct.unpack_from('<H', frame, offset + 2)[0]
        spd_raw = struct.unpack_from('<H', frame, offset + 4)[0]
        x = decode_coord(x_raw)
        y = decode_coord(y_raw)
        speed = decode_coord(spd_raw)
        if x != 0 or y != 0:
            targets.append({'x': x, 'y': y, 'speed': speed})

    return targets

buf = bytearray()
while True:
    buf += s.read(64)
    if len(buf) > 128:
        targets = parse_frame(buf)
        if targets is not None:
            for i, t in enumerate(targets):
                print(f"Cible {i+1}: X={t['x']:.2f}m Y={t['y']:.2f}m Speed={t['speed']:.2f}m/s")
            if not targets:
                print("Aucune cible")
            buf = bytearray()
        if len(buf) > 512:
            buf = bytearray()
    time.sleep(0.01)
