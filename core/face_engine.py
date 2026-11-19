"""Face detection, encoding and matching.

Detection uses dlib's HOG + linear-SVM detector; each detected face is turned
into a 128-dimensional embedding by dlib's ResNet-34 metric-learning model
(through the face_recognition wrapper). Identity is decided by the smallest
Euclidean distance between the live embedding and the enrolled gallery.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import face_recognition
import numpy as np

import config


@dataclass
class Detection:
    box: tuple                       # (top, right, bottom, left) in original frame pixels
    student_id: int | None = None
    matric: str | None = None
    name: str = "Unknown"
    distance: float | None = None
    note: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def recognised(self) -> bool:
        return self.student_id is not None


@dataclass
class SampleResult:
    ok: bool
    message: str
    encoding: np.ndarray | None = None
    box: tuple | None = None


class FaceEngine:
    def __init__(self, tolerance: float | None = None, scale: float | None = None, model: str = "hog"):
        self.tolerance = config.TOLERANCE if tolerance is None else tolerance
        self.scale = config.DETECT_SCALE if scale is None else scale
        self.model = model
        self._enc = np.empty((0, 128))
        self._owner = np.empty(0, dtype=int)
        self._ids: list[int] = []
        self._matrics: list[str] = []
        self._names: list[str] = []

    # ------------------------------------------------------------- gallery
    def load_gallery(self, entries) -> None:
        """entries: iterable of (student_id, matric, display_name, ndarray[N, 128])."""
        blocks, owners = [], []
        self._ids, self._matrics, self._names = [], [], []
        for idx, (sid, matric, name, enc) in enumerate(entries):
            enc = np.atleast_2d(np.asarray(enc, dtype=np.float64))
            if enc.shape[1] != 128 or not len(enc):
                continue
            self._ids.append(sid); self._matrics.append(matric); self._names.append(name)
            blocks.append(enc)
            owners.extend([len(self._ids) - 1] * len(enc))
        self._enc = np.vstack(blocks) if blocks else np.empty((0, 128))
        self._owner = np.asarray(owners, dtype=int)

    @property
    def gallery_size(self) -> int:
        return len(self._ids)

    # ----------------------------------------------------------- detection
    def detect(self, bgr: np.ndarray) -> list[tuple]:
        small = bgr if self.scale == 1 else cv2.resize(bgr, (0, 0), fx=self.scale, fy=self.scale)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        boxes = face_recognition.face_locations(rgb, model=self.model)
        return [tuple(int(round(v / self.scale)) for v in b) for b in boxes]

    def encode(self, bgr: np.ndarray, boxes: list[tuple]) -> list[np.ndarray]:
        if not boxes:
            return []
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        return face_recognition.face_encodings(rgb, boxes, num_jitters=1)

    # ------------------------------------------------------------ matching
    def match(self, encoding: np.ndarray) -> tuple[int | None, float | None]:
        """Return (gallery index, distance) or (None, best distance) when nobody is close enough."""
        if not len(self._enc):
            return None, None
        dist = np.linalg.norm(self._enc - encoding, axis=1)
        best = int(np.argmin(dist))
        d = float(dist[best])
        return (int(self._owner[best]), d) if d <= self.tolerance else (None, d)

    def process_frame(self, bgr: np.ndarray) -> list[Detection]:
        boxes = self.detect(bgr)
        out = []
        for box, enc in zip(boxes, self.encode(bgr, boxes)):
            idx, dist = self.match(enc)
            if idx is None:
                out.append(Detection(box=box, distance=dist))
            else:
                out.append(Detection(box=box, student_id=self._ids[idx], matric=self._matrics[idx],
                                     name=self._names[idx], distance=dist))
        return out

    # ----------------------------------------------------------- enrolment
    def enrol_sample(self, bgr: np.ndarray) -> SampleResult:
        """Quality-gate one frame: exactly one face, large enough, then encode it."""
        boxes = self.detect(bgr)
        if not boxes:
            return SampleResult(False, "No face detected - face the camera directly.")
        if len(boxes) > 1:
            return SampleResult(False, "More than one face in view - only the student should be visible.")
        top, right, bottom, left = boxes[0]
        if bottom - top < config.MIN_FACE_PIXELS:
            return SampleResult(False, "Face too small - move closer to the camera.", box=boxes[0])
        enc = self.encode(bgr, boxes)
        if not enc:
            return SampleResult(False, "Could not encode the face - try again.", box=boxes[0])
        return SampleResult(True, "Sample captured.", encoding=enc[0], box=boxes[0])
