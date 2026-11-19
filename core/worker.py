"""Background recognition thread so the GUI never freezes while dlib is working."""
from __future__ import annotations

import threading
import time


class RecognitionWorker(threading.Thread):
    """Keeps only the newest frame (older ones are dropped) and publishes the latest result."""

    def __init__(self, engine):
        super().__init__(daemon=True, name="recognition-worker")
        self.engine = engine
        self._frame = None
        self._cv = threading.Condition()
        self._running = True
        self._result = None
        self.version = 0
        self.latency_ms = 0.0

    def submit(self, frame) -> None:
        with self._cv:
            self._frame = frame
            self._cv.notify()

    def take(self):
        """Return the latest detections list."""
        return self._result or []

    def run(self) -> None:
        while self._running:
            with self._cv:
                while self._frame is None and self._running:
                    self._cv.wait(0.2)
                frame, self._frame = self._frame, None
            if frame is None:
                continue
            t0 = time.perf_counter()
            try:
                dets = self.engine.process_frame(frame)
            except Exception:           # a bad frame must never kill the thread
                dets = []
            self.latency_ms = (time.perf_counter() - t0) * 1000.0
            self._result = dets
            self.version += 1

    def stop(self) -> None:
        self._running = False
        with self._cv:
            self._cv.notify_all()
