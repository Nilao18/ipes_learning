"""Detection de personnes YOLOv8n-person en processus separe."""
import os
import time
import multiprocessing as mp

import numpy as np

MODEL_PATH = os.path.expanduser('~/ipes/models/yolov8n-person.onnx')
INPUT_SIZE = 640
CONF_SEUIL = 0.25
IOU_SEUIL = 0.45


def _preprocess(frame):
    """BGR HxWx3 -> tenseur 1x3x640x640 + facteurs de remise a l'echelle."""
    import cv2
    frame = cv2.flip(frame, -1)
    h, w = frame.shape[:2]
    r = min(INPUT_SIZE / w, INPUT_SIZE / h)
    nw, nh = int(w * r), int(h * r)
    resized = cv2.resize(frame, (nw, nh))
    canvas = np.full((INPUT_SIZE, INPUT_SIZE, 3), 114, dtype=np.uint8)
    dx, dy = (INPUT_SIZE - nw) // 2, (INPUT_SIZE - nh) // 2
    canvas[dy:dy + nh, dx:dx + nw] = resized
    x = canvas[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    return np.ascontiguousarray(x[None]), r, dx, dy


def _nms(boxes, scores):
    """Suppression des non-maxima, retourne les indices gardes."""
    if len(boxes) == 0:
        return []
    x1, y1 = boxes[:, 0], boxes[:, 1]
    x2, y2 = boxes[:, 0] + boxes[:, 2], boxes[:, 1] + boxes[:, 3]
    aires = (x2 - x1) * (y2 - y1)
    ordre = scores.argsort()[::-1]
    gardes = []
    while ordre.size > 0:
        i = ordre[0]
        gardes.append(i)
        xx1 = np.maximum(x1[i], x1[ordre[1:]])
        yy1 = np.maximum(y1[i], y1[ordre[1:]])
        xx2 = np.minimum(x2[i], x2[ordre[1:]])
        yy2 = np.minimum(y2[i], y2[ordre[1:]])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        iou = inter / (aires[i] + aires[ordre[1:]] - inter + 1e-9)
        ordre = ordre[1:][iou < IOU_SEUIL]
    return gardes


def _postprocess(sortie, r, dx, dy, w, h):
    """Sortie 1x5x8400 -> liste de (x, y, largeur, hauteur, score) en pixels image."""
    pred = sortie[0][0].T                      # 8400 x 5
    scores = pred[:, 4]
    masque = scores > CONF_SEUIL
    pred, scores = pred[masque], scores[masque]
    if len(pred) == 0:
        return []
    cx, cy, bw, bh = pred[:, 0], pred[:, 1], pred[:, 2], pred[:, 3]
    boxes = np.stack([
        (cx - bw / 2 - dx) / r,
        (cy - bh / 2 - dy) / r,
        bw / r,
        bh / r,
    ], axis=1)
    res = []
    for i in _nms(boxes, scores):
        x, y, bw_, bh_ = boxes[i]
        res.append((
            max(0, int(x)), max(0, int(y)),
            min(int(bw_), w), min(int(bh_), h),
            float(scores[i]),
        ))
    return res


VIGNETTE_W = 120
VIGNETTE_H = 160


def _crop(frame, dets):
    """Decoupe la detection la plus confiante et la met au format vignette."""
    import cv2
    x, y, bw, bh, _ = max(dets, key=lambda d: d[4])
    h, w = frame.shape[:2]
    marge = int(bw * 0.15)
    x1 = max(0, x - marge)
    y1 = max(0, y - marge)
    x2 = min(w, x + bw + marge)
    y2 = min(h, y + bh + marge)
    if x2 - x1 < 10 or y2 - y1 < 10:
        return None
    return cv2.resize(frame[y1:y2, x1:x2], (VIGNETTE_W, VIGNETTE_H))


def _worker(entree, sortie):
    """Processus dedie : charge le modele puis boucle sur la queue."""
    import onnxruntime as ort
    import cv2
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 2
    session = ort.InferenceSession(
        MODEL_PATH, opts, providers=['CPUExecutionProvider'])
    nom_entree = session.get_inputs()[0].name
    while True:
        item = entree.get()
        if item is None:
            break
        frame, cote = item
        try:
            h, w = frame.shape[:2]
            x, r, dx, dy = _preprocess(frame)
            t0 = time.time()
            out = session.run(None, {nom_entree: x})
            dets = _postprocess(out, r, dx, dy, w, h)
            vignette = _crop(cv2.flip(frame, -1), dets) if dets else None
            sortie.put((cote, dets, (time.time() - t0) * 1000, vignette))
        except Exception as e:
            print("WORKER ERREUR:", e, flush=True)
            sortie.put((cote, [], 0.0, None))


class PersonDetector:
    """Interface non bloquante : submit() envoie, poll() recupere."""

    def __init__(self):
        import multiprocessing.spawn as _spawn
        _orig = _spawn.get_preparation_data
        def _clean(name):
            d = _orig(name)
            d.pop('init_main_from_path', None)
            d.pop('init_main_from_name', None)
            return d
        _spawn.get_preparation_data = _clean
        ctx = mp.get_context('spawn')
        self.entree = ctx.Queue(maxsize=2)
        self.sortie = ctx.Queue()
        self.proc = ctx.Process(
            target=_worker, args=(self.entree, self.sortie), daemon=True)
        self.proc.start()
        self.detections = {'L': [], 'R': []}
        self.vignettes = {'L': None, 'R': None}
        self.horodatage = {'L': 0.0, 'R': 0.0}
        self.latence = 0.0
        self.en_cours = False

    def submit(self, frame, cote):
        """Envoie une frame si le worker est libre."""
        if self.en_cours or frame is None:
            return False
        try:
            self.entree.put_nowait((frame.copy(), cote))
            self.en_cours = True
            return True
        except Exception:
            return False

    def poll(self):
        """Recupere les resultats disponibles sans bloquer."""
        while not self.sortie.empty():
            cote, dets, ms, vign = self.sortie.get()
            self.detections[cote] = dets
            self.vignettes[cote] = vign
            self.horodatage[cote] = time.time()
            self.latence = ms
            self.en_cours = False

    def compte(self, cote, duree=3.0):
        """Nombre de personnes detectees recemment sur un cote."""
        if time.time() - self.horodatage[cote] > duree:
            return 0
        return len(self.detections[cote])

    def vignette(self, cote, duree=3.0):
        """Imagette de la derniere personne detectee, ou None."""
        if time.time() - self.horodatage[cote] > duree:
            return None
        return self.vignettes[cote]

    def stop(self):
        try:
            self.entree.put_nowait(None)
        except Exception:
            pass
