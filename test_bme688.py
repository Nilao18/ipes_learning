from adafruit_extended_bus import ExtendedI2C as I2C
import adafruit_bme680
import time

i2c = I2C(1)
bme = adafruit_bme680.Adafruit_BME680_I2C(i2c, address=0x77)

bme.sea_level_pressure = 1013.25

while True:
    print(f"Température : {bme.temperature:.1f}°C")
    print(f"Humidité    : {bme.humidity:.1f}%")
    print(f"Pression    : {bme.pressure:.1f} hPa")
    print(f"Altitude    : {bme.altitude:.1f} m")
    print(f"Gaz (VOC)   : {bme.gas:.0f} Ω")
    print("---")
    time.sleep(2)
