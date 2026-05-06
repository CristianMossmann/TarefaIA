from __future__ import annotations

import os
import threading
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import cv2
from ultralytics import YOLO

from services.event_repository import EventRepository


class VideoMonitor:
    def __init__(
        self,
        camera_source,
        model_path: str,
        confidence_threshold: float,
        target_classes: set[str],
        min_consecutive_frames: int,
        alert_cooldown_seconds: int,
        reconnect_seconds: int,
        save_dir: Path,
        event_repository: EventRepository,
    ):
        self.camera_source = camera_source
        self.confidence_threshold = confidence_threshold
        self.target_classes = target_classes
        self.min_consecutive_frames = min_consecutive_frames
        self.alert_cooldown_seconds = alert_cooldown_seconds
        self.reconnect_seconds = reconnect_seconds
        self.save_dir = save_dir
        self.event_repository = event_repository

        self.model = YOLO(model_path)

        self.last_frame = None
        self.last_frame_lock = threading.Lock()

        self.detection_state = defaultdict(int)
        self.last_alert_time = defaultdict(lambda: 0.0)

        self._running = False
        self._thread: threading.Thread | None = None
        self._connected = False
        self._source_type = self._detect_source_type(camera_source)

    @staticmethod
    def _detect_source_type(source) -> str:
        if isinstance(source, int):
            return "camera"
        source_str = str(source).lower()
        if source_str.startswith("rtsp://"):
            return "rtsp"
        if source_str.startswith("http"):
            return "stream"
        return "file"

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _draw_box(self, frame, x1, y1, x2, y2, label, conf):
        text = f"{label} {conf:.2f}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 2)
        cv2.putText(
            frame,
            text,
            (x1, max(20, y1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 200, 0),
            2,
        )

    def _should_alert(self, label: str) -> bool:
        now = time.time()
        return (now - self.last_alert_time[label]) > self.alert_cooldown_seconds

    def _run(self) -> None:
        while self._running:
            cap = cv2.VideoCapture(self.camera_source)
            self._connected = cap.isOpened()

            if not self._connected:
                print("[camera] Falha ao abrir fonte. Tentando reconectar...")
                time.sleep(self.reconnect_seconds)
                continue

            print("[camera] Fonte iniciada com sucesso.")

            while self._running:
                ok, frame = cap.read()
                if not ok:
                    self._connected = False
                    print("[camera] Stream indisponivel. Reconectando...")
                    break

                self._connected = True
                self._process_frame(frame)
                time.sleep(0.05)

            cap.release()
            if self._running:
                time.sleep(self.reconnect_seconds)

    def _process_frame(self, frame) -> None:
        results = self.model(frame, conf=self.confidence_threshold, verbose=False)

        found_labels_in_frame = set()
        best_conf_by_label = {}

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                label = self.model.names[cls_id]

                if label not in self.target_classes:
                    continue

                found_labels_in_frame.add(label)
                if label not in best_conf_by_label or conf > best_conf_by_label[label]:
                    best_conf_by_label[label] = conf

                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                self._draw_box(frame, x1, y1, x2, y2, label, conf)

        for label in self.target_classes:
            if label in found_labels_in_frame:
                self.detection_state[label] += 1
            else:
                self.detection_state[label] = 0

        for label in found_labels_in_frame:
            if (
                self.detection_state[label] >= self.min_consecutive_frames
                and self._should_alert(label)
            ):
                self._save_alert_frame(frame, label, best_conf_by_label.get(label, 0.0))
                self.last_alert_time[label] = time.time()

        with self.last_frame_lock:
            self.last_frame = frame.copy()

    def _save_alert_frame(self, frame, label: str, confidence: float) -> None:
        event_id = datetime.now().strftime("%H%M%S")
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{label}_{event_id}.jpg"
        filepath = self.save_dir / filename

        os.makedirs(self.save_dir, exist_ok=True)
        cv2.imwrite(str(filepath), frame)
        image_path = f"/static/captures/{filename}"

        self.event_repository.save_event(label, confidence, image_path)
        print(f"[ALERTA] {label} detectado. Evidencia salva em {filepath}")

    def get_last_frame_jpeg(self) -> bytes | None:
        with self.last_frame_lock:
            if self.last_frame is None:
                return None
            success, buffer = cv2.imencode(".jpg", self.last_frame)
            if not success:
                return None
            return buffer.tobytes()

    def frame_generator(self):
        while True:
            frame_bytes = self.get_last_frame_jpeg()
            if frame_bytes is None:
                time.sleep(0.15)
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
            time.sleep(0.12)

    def status(self) -> dict:
        return {
            "online": self._connected,
            "connected": self._connected,
            "has_live_frame": self.last_frame is not None,
            "source_type": self._source_type,
            "source": str(self.camera_source),
        }
