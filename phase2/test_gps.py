import serial
import pynmea2

s = serial.Serial('/dev/ttyTHS1', 9600, timeout=2)
print("GPS connecté, en attente de fix...")

while True:
    try:
        line = s.readline().decode('ascii', errors='replace').strip()
        if line.startswith('$GNGGA') or line.startswith('$GNRMC'):
            msg = pynmea2.parse(line)
            if line.startswith('$GNGGA'):
                print(f"Satellites: {msg.num_sats} | Fix: {msg.gps_qual} | Alt: {msg.altitude}m")
            elif line.startswith('$GNRMC') and msg.status == 'A':
                print(f"LAT: {msg.latitude:.6f} | LON: {msg.longitude:.6f} | Vitesse: {msg.spd_over_grnd} kts")
    except Exception as e:
        pass
