import cv2
import numpy as np
import math
import os
from PIL import Image

TILES_DIR = "/home/quentin/ipes/maps/tours"

def deg2tile(lat, lon, zoom):
    lat_r = math.radians(lat)
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(lat_r) + 1/math.cos(lat_r)) / math.pi) / 2 * n)
    return x, y

def deg2pixel_offset(lat, lon, lat_center, lon_center, zoom, tile_size=256):
    x_tile, y_tile = deg2tile(lat_center, lon_center, zoom)
    x, y = deg2tile(lat, lon, zoom)
    
    n = 2 ** zoom
    px_center = int((lon_center + 180) / 360 * n * tile_size)
    py_center = int((1 - math.log(math.tan(math.radians(lat_center)) + 
                    1/math.cos(math.radians(lat_center))) / math.pi) / 2 * n * tile_size)
    
    px = int((lon + 180) / 360 * n * tile_size)
    py = int((1 - math.log(math.tan(math.radians(lat)) + 
              1/math.cos(math.radians(lat))) / math.pi) / 2 * n * tile_size)
    
    return px - px_center, py - py_center

def get_minimap(lat, lon, zoom=14, size=400):
    x_tile, y_tile = deg2tile(lat, lon, zoom)
    
    # Charger 3x3 tuiles autour de la position
    canvas = np.zeros((size, size, 3), dtype=np.uint8)
    tile_size = 256
    
    for dx in range(-1, 2):
        for dy in range(-1, 2):
            tx = x_tile + dx
            ty = y_tile + dy
            path = os.path.join(TILES_DIR, str(zoom), str(tx), f"{ty}.png")
            
            if not os.path.exists(path):
                continue
            
            img = np.array(Image.open(path).convert('RGB'))
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            
            # Position sur le canvas
            cx = size//2 + dx * tile_size
            cy = size//2 + dy * tile_size
            
            # Clip et colle
            x1 = max(0, cx - tile_size//2)
            y1 = max(0, cy - tile_size//2)
            x2 = min(size, cx + tile_size//2)
            y2 = min(size, cy + tile_size//2)
            
            sx1 = max(0, tile_size//2 - cx)
            sy1 = max(0, tile_size//2 - cy)
            
            if x2 > x1 and y2 > y1:
                canvas[y1:y2, x1:x2] = img[sy1:sy1+(y2-y1), sx1:sx1+(x2-x1)]
    
    # Marqueur position (triangle)
    cv2.circle(canvas, (size//2, size//2), 6, (0, 0, 255), -1)
    cv2.circle(canvas, (size//2, size//2), 8, (255, 255, 255), 2)
    
    return canvas

# Test
LAT = 47.3941
LON = 0.6848

minimap = get_minimap(LAT, LON, zoom=14, size=400)
cv2.imwrite('/tmp/minimap_test.jpg', minimap)
print("Minimap sauvegardée dans /tmp/minimap_test.jpg")
