# probe_write_limit.py
import smbus2
from smbus2 import i2c_msg
import time

BUS, ADDR = 7, 0x42
bus = smbus2.SMBus(BUS)

# Test : poll MON-VER (8 octets, on sait que ça marche)
print("=== Test 8 octets (MON-VER) ===")
frame = [0xB5, 0x62, 0x0A, 0x04, 0x00, 0x00, 0x0E, 0x34]
bus.i2c_rdwr(i2c_msg.write(ADDR, frame))
time.sleep(0.5)
read = i2c_msg.read(ADDR, 50)
bus.i2c_rdwr(read)
data = bytes(read)
ok = b'\xb5\x62\x0a\x04' in data
print(f"  Réponse MON-VER: {'✅' if ok else '❌'}")
print(f"  Bytes: {data[:20].hex()}")

# Test : poll MON-HW (8 octets aussi mais autre commande)
print("\n=== Test 8 octets (MON-HW) ===")
frame = [0xB5, 0x62, 0x0A, 0x09, 0x00, 0x00, 0x13, 0x43]
bus.i2c_rdwr(i2c_msg.write(ADDR, frame))
time.sleep(0.5)
read = i2c_msg.read(ADDR, 80)
bus.i2c_rdwr(read)
data = bytes(read)
ok = b'\xb5\x62\x0a\x09' in data
print(f"  Réponse MON-HW: {'✅' if ok else '❌'}")
print(f"  Bytes: {data[:20].hex()}")
