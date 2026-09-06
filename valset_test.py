# valset_test.py
import smbus2
from smbus2 import i2c_msg
import time

BUS, ADDR = 7, 0x42
bus = smbus2.SMBus(BUS)

# CFG-VALSET : I2COUTPROT-NMEA = 1, layer RAM
frame = [0xB5, 0x62, 0x06, 0x8A, 0x09, 0x00,
         0x00, 0x01, 0x00, 0x00,
         0x02, 0x00, 0x72, 0x10, 0x01,
         0x29, 0x85]

print(f"Sending {len(frame)} bytes: {bytes(frame).hex()}")
write = i2c_msg.write(ADDR, frame)
bus.i2c_rdwr(write)

time.sleep(0.3)

# Lire la réponse
read = i2c_msg.read(ADDR, 30)
bus.i2c_rdwr(read)
data = bytes(read)
print(f"Response: {data.hex()}")

# Chercher l'ACK dans la réponse
for i in range(len(data) - 7):
    if data[i:i+4] == b'\xb5\x62\x05\x01':
        print(f"✅ ACK reçu à l'offset {i}: class=0x{data[i+6]:02x} id=0x{data[i+7]:02x}")
        break
    elif data[i:i+4] == b'\xb5\x62\x05\x00':
        print(f"❌ NACK reçu à l'offset {i}: class=0x{data[i+6]:02x} id=0x{data[i+7]:02x}")
        break
else:
    print("⚠️  Pas d'ACK/NACK trouvé dans la réponse (probablement frame pas reçu)")
