"""Shared image/video/camera pipeline. No GUI calls from the worker."""
from collections import Counter
from datetime import datetime
from pathlib import Path
import csv
import json
import math
import threading
import time
import uuid

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
LABELS = {'head': 'Baretsiz bas', 'helmet': 'Baret', 'person': 'Kisi', 'uncertain': 'Kararsiz'}
COLORS = {'head': (60, 70, 230), 'helmet': (90, 190, 40), 'person': (220, 170, 60), 'uncertain': (0, 190, 255)}


def resolve_conflicts(detections):
    """Abstain when mutually exclusive classes overlap the same head."""
    def iou(a, b):
        overlap = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
        union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - overlap
        return overlap / max(union, 1e-9)
    used = set()
    result = []
    for i, detection in enumerate(detections):
        if i in used:
            continue
        conflicting = [j for j, other in enumerate(detections) if j > i and j not in used
                       and {detection['class'], other['class']} == {'head', 'helmet'}
                       and iou(detection['box'], other['box']) >= .6]
        if conflicting:
            group = [detection] + [detections[j] for j in conflicting]
            best = max(group, key=lambda d: d['confidence'])
            result.append({**best, 'class': 'uncertain', 'alternatives': group})
            used.update(conflicting)
        else:
            result.append(detection)
    return result


def read_image(path):
    frame = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError('Fotoğraf okunamadı. Geçerli bir görsel seçin.')
    return frame


def save_image(path, frame):
    ok, data = cv2.imencode('.jpg', frame)
    if not ok:
        raise RuntimeError('Fotoğraf kodlanamadı.')
    data.tofile(str(path))


class Detector:
    def __init__(self, path):
        from ultralytics import YOLO
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f'Model bulunamadı: {path}')
        self.model = YOLO(str(path), task='detect')
        self.names = {int(k): str(v).lower() for k, v in self.model.names.items()}
        if not {'head', 'helmet'}.issubset(self.names.values()):
            raise ValueError('Bu model head ve helmet sınıflarını içermiyor. Eğitilmiş baret modelini seçin.')

    def detect(self, frame, confidence):
        result = self.model.predict(frame, conf=confidence, imgsz=320, verbose=False, device='cpu')[0]
        annotated = frame.copy()
        detections = []
        if result.boxes is not None:
            for box, score, cls in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist(), result.boxes.cls.cpu().tolist()):
                name = self.names[int(cls)]
                detections.append({'class': name, 'confidence': round(score, 5), 'box': box})
        detections = resolve_conflicts(detections)
        for detection in detections:
            name, score, box = detection['class'], detection['confidence'], detection['box']
            x1, y1, x2, y2 = map(int, box)
            color = COLORS.get(name, (180, 180, 180))
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            label = LABELS.get(name, name) if name == 'uncertain' else f'{LABELS.get(name, name)} {score:.0%}'
            cv2.putText(annotated, label, (x1, max(20, y1 - 7)), cv2.FONT_HERSHEY_SIMPLEX, .55, color, 2)
        return annotated, detections


def process(source, kind, model_path, output_root, confidence=.5, stop=None, callback=None, detector=None, max_frames=None, event_store=None, event_callback=None, tracker=None, show_opencv=False, on_quit=None, save_media=True):
    if kind not in ('image', 'video', 'camera'):
        raise ValueError('Bilinmeyen kaynak türü.')
    if not 0 < confidence <= 1:
        raise ValueError('Güven eşiği 0 ile 1 arasında olmalı.')
    stop = stop or threading.Event()
    detector = detector or Detector(model_path)
    monitor = None
    if event_store is not None and kind != 'image':
        from .violations import ViolationMonitor
        from .tracking import PersonTracker
        tracker = tracker or PersonTracker(ROOT / 'original' / 'yolov8n.pt')
        monitor = ViolationMonitor(event_store, f'Kamera {source}' if kind == 'camera' else str(source))
    folder = Path(output_root) / (datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6])
    folder.mkdir(parents=True, exist_ok=False)
    capture = writer = None
    count = 0
    fps = 0.0
    totals = Counter()
    status = 'completed'
    error = None
    window_open = False
    event_count = 0
    start = time.monotonic()
    try:
        if kind == 'image':
            frame = read_image(source)
            total = 1
        else:
            capture = cv2.VideoCapture(int(source) if kind == 'camera' else str(source))
            if not capture.isOpened():
                raise RuntimeError('Kamera/video açılamadı. Dosyayı veya kamera numarasını kontrol edin.')
            fps = capture.get(cv2.CAP_PROP_FPS)
            if not math.isfinite(fps) or fps <= 0 or fps > 240:
                fps = 25.0
            total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) if kind == 'video' else 0
        with (folder / 'detections.csv').open('w', encoding='utf-8-sig', newline='') as f:
            report = csv.writer(f)
            report.writerow(['frame', 'seconds', 'class', 'confidence', 'x1', 'y1', 'x2', 'y2'])
            while not stop.is_set():
                if kind != 'image':
                    ok, frame = capture.read()
                    if not ok:
                        if kind == 'camera' or count == 0 or (total > 0 and count < total):
                            raise RuntimeError('Görüntü akışı beklenmedik şekilde kesildi veya okunamadı.')
                        break
                annotated, detections = detector.detect(frame, confidence)
                if monitor is not None:
                    from .tracking import PersonTracker
                    tracks = tracker.update(frame, detections)
                    annotated = frame.copy()
                    PersonTracker.draw(annotated, tracks)
                    new_events = monitor.update(tracks, annotated)
                    event_count += len(new_events)
                    for event in new_events:
                        if event_callback:
                            event_callback(event)
                seconds = (time.monotonic() - start) if kind == 'camera' else (count / fps if fps else 0)
                count += 1
                counts = Counter(d['class'] for d in detections)
                if monitor is not None:
                    counts = Counter(t['state'] for t in tracks)
                    counts['person'] = len(tracks)
                totals.update(counts)
                for d in detections:
                    report.writerow([count, round(seconds, 3), d['class'], d['confidence'], *d['box']])
                if kind == 'image':
                    save_image(folder / 'sonuc.jpg', annotated)
                elif save_media:
                    if writer is None:
                        h, w = annotated.shape[:2]
                        writer = cv2.VideoWriter(str(folder / 'sonuc.mp4'), cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
                        if not writer.isOpened():
                            raise RuntimeError('MP4 kaydı başlatılamadı. Çıktı klasörünü kontrol edin.')
                    writer.write(annotated)
                if callback:
                    callback(annotated, dict(counts), count, total)
                if show_opencv:
                    cv2.imshow('Baret Tespit - Q ile cikis', annotated)
                    window_open = True
                    key = cv2.waitKey(1) & 0xff
                    if key in (ord('q'), ord('Q')) or cv2.getWindowProperty('Baret Tespit - Q ile cikis', cv2.WND_PROP_VISIBLE) < 1:
                        stop.set()
                        if on_quit:
                            on_quit()
                        break
                if kind == 'image' or (max_frames and count >= max_frames):
                    break
            if stop.is_set():
                status = 'stopped'
    except Exception as exc:
        status, error = 'failed', str(exc)
        raise
    finally:
        if capture is not None:
            capture.release()
        if writer is not None:
            writer.release()
        if window_open:
            try:
                cv2.destroyWindow('Baret Tespit - Q ile cikis')
            except cv2.error:
                pass  # User may already have closed the native window.
        summary = {'status': status, 'error': error, 'source': str(source), 'kind': kind, 'model': str(model_path), 'confidence': confidence, 'frames': count, 'fps': fps, 'elapsed_seconds': round(time.monotonic() - start, 2), 'detections_across_frames': dict(totals), 'new_events': event_count, 'session_id': monitor.session_id if monitor else None, 'note': 'Kareler toplamı benzersiz kişi sayısı değildir. Video ses içermez. Kamera kaydı nominal FPS ile yazılır; işleme hızına göre zaman ölçeği değişebilir.'}
        (folder / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return folder
