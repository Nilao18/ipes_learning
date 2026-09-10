#-----------------------------------------------------------------------------------
# OCR - Transcription de texte, processus separe pour contourner le GIL
#-----------------------------------------------------------------------------------
import multiprocessing as mp


# -------------------------------------------------------------------------------Detection de texte
def ocr_worker(input_queue, output_queue):
    """Processus separe pour l'OCR - contourne le GIL."""
    from onnxtr.models import ocr_predictor
    from onnxtr.io import DocumentFile
    import cv2

    model = ocr_predictor(
        det_arch="db_mobilenet_v3_large",
        reco_arch="crnn_mobilenet_v3_small"
    )
    while True:
        frame = input_queue.get()
        if frame is None:
            break
        try:
            tmp = '/tmp/ipes_ocr_frame.png'
            cv2.imwrite(tmp, frame)
            doc = DocumentFile.from_images(tmp)
            result = model(doc)
            text = result.render().strip()
            lines = [l for l in text.split('\n') if len(l.strip()) > 2]
            output_queue.put(' | '.join(lines[-2:]) if lines else "")
        except Exception:
            output_queue.put("")


#-----------------------------------------------------------------------------------
# Interface non bloquante : submit() envoie une frame, poll() recupere le texte
#-----------------------------------------------------------------------------------
class OCRProcess:
    def __init__(self):
        print("Init OCR...")
        self.input_queue = mp.Queue(maxsize=1)
        self.output_queue = mp.Queue(maxsize=1)
        self.process = mp.Process(
            target=ocr_worker,
            args=(self.input_queue, self.output_queue),
            daemon=True
        )
        self.process.start()
        self.text = ""
        self.busy = False
        print("OCR OK")

    def submit(self, frame):
        if not self.busy and not self.input_queue.full():
            self.input_queue.put(frame.copy())
            self.busy = True

    def poll(self):
        if self.busy and not self.output_queue.empty():
            self.text = self.output_queue.get()
            self.busy = False

    def stop(self):
        self.input_queue.put(None)
        self.process.join(timeout=3)
