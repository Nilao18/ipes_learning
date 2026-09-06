import smbus2
from smbus2 import i2c_msg
import time

BUS, ADDR = 7, 0x42
bus = smbus2.SMBus(BUS)

def read_available():
    # Write register pointer 0xFD, then read 2 bytes — as one transaction
    write = i2c_msg.write(ADDR, [0xFD])
    read = i2c_msg.read(ADDR, 2)
    bus.i2c_rdwr(write, read)
    data = list(read)
    return (data[0] << 8) | data[1]

def read_stream(n):
    # Pure read — MAX-M10S returns data-stream bytes (register 0xFF auto)
    read = i2c_msg.read(ADDR, n)
    bus.i2c_rdwr(read)
    return bytes(read)

buf = bytearray()
print("reading via i2c_rdwr…")
for i in range(40):
    n = read_available()
    print(f"  available: {n}")
    if 0 < n < 1024:           # sanity: ignore obviously-bad counts
        chunks_to_read = min(n, 256)
        data = read_stream(chunks_to_read)
        buf.extend(data)
        # show first few bytes raw so we can see what's coming
        print(f"  first 16 bytes: {data[:16].hex()} {data[:16]!r}")
        while b'\r\n' in buf:
            line, buf = buf.split(b'\r\n', 1)
            if line.startswith(b'$'):
                print(f"  NMEA: {line.decode(errors='ignore')}")
    time.sleep(0.5)
