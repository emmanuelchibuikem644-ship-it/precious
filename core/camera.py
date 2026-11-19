"""Frame sources. WebcamSource wraps OpenCV's VideoCapture; FileSource replays a
video or still image (useful for demonstrations and automated tests)."""
from __future__ import annotations

import cv2


class WebcamSource:
    def __init__(self, index: int = 0, width: int = 640, height: int = 480):
        self.index, self.width, self.height = index, width, height
        self.name = f"Webcam {index}"
        self._cap = None

    def open(self) -> bool:
        self._cap = cv2.VideoCapture(self.index)
        if self._cap is not None and self._cap.isOpened():
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            return True
        return False

    def read(self):
        if self._cap is None:
            return None
        ok, frame = self._cap.read()
        return frame if ok else None

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class FileSource:
    """Loops over a video file, or repeats a single image."""

    def __init__(self, path: str):
        self.path = path
        self.name = f"File: {path}"
        self._cap = None
        self._still = None

    def open(self) -> bool:
        img = cv2.imread(self.path)
        if img is not None:
            self._still = img
            return True
        self._cap = cv2.VideoCapture(self.path)
        return bool(self._cap and self._cap.isOpened())

    def read(self):
        if self._still is not None:
            return self._still.copy()
        ok, frame = self._cap.read()
        if not ok:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._cap.read()
        return frame if ok else None

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
