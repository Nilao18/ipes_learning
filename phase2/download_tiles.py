import os
import requests
import math

def deg2tile(lat, lon, zoom):
    lat_r = math.radians(lat)
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(lat_r) + 1/math.cos(lat_r)) / math.pi) / 2 * n)
    return x, y

def download_tiles(lat_center, lon_center, zoom_levels, radius_km, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    headers = {'User-Agent': 'IPES-HUD/1.0 (educational project)'}
    
    for zoom in zoom_levels:
        # Convertir rayon en degrés approximatif
        x_center, y_center = deg2tile(lat_center, lon_center, zoom)
        tiles_radius = max(1, int(radius_km * (2**zoom) / (40075 * math.cos(math.radians(lat_center)))))
        x_min = x_center - tiles_radius
        x_max = x_center + tiles_radius
        y_min = y_center - tiles_radius
        y_max = y_center + tiles_radius
        total = (x_max - x_min + 1) * (y_max - y_min + 1)

        count = 0

        print(f"Zoom {zoom}: {total} tuiles à télécharger")
        
        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                tile_dir = os.path.join(output_dir, str(zoom), str(x))
                os.makedirs(tile_dir, exist_ok=True)
                tile_path = os.path.join(tile_dir, f"{y}.png")
                
                if os.path.exists(tile_path):
                    count += 1
                    continue
                
                url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"
                try:
                    r = requests.get(url, headers=headers, timeout=10)
                    if r.status_code == 200:
                        with open(tile_path, 'wb') as f:
                            f.write(r.content)
                        count += 1
                        print(f"Zoom {zoom}: {count}/{total}", end='\r')
                except Exception as e:
                    print(f"Erreur {url}: {e}")
    
    print(f"\nTéléchargement terminé.")

# Centre = Tours
LAT = 47.3941
LON = 0.6848
ZOOM_LEVELS = [13, 14, 15]  # 13=vue large, 15=détail rues
RADIUS_KM = 5
OUTPUT_DIR = "/home/quentin/ipes/maps/tours"

download_tiles(LAT, LON, ZOOM_LEVELS, RADIUS_KM, OUTPUT_DIR)
