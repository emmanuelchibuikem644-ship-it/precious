"""Demonstration / test harness (NOT part of the production code path).

* seed_demo()               - fictional staff, students, courses and attendance history
* SyntheticClassroomSource  - anonymised silhouette "camera" so the GUI can be demonstrated without a webcam
* ScriptedEngine            - stands in for FaceEngine and reports the identities that the synthetic scene contains

Everything here uses invented sample data only.
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta

import cv2
import numpy as np

import config
from core.face_engine import Detection, SampleResult

STUDENTS = [
    ("CSC/2023/001", "Chioma", "Nwankwo"), ("CSC/2023/002", "Tamuno", "Briggs"),
    ("CSC/2023/003", "Emeka", "Eze"), ("CSC/2023/004", "Ibinabo", "Amadi"),
    ("CSC/2023/005", "Blessing", "Okafor"), ("CSC/2023/006", "Oluwaseun", "Adeyemi"),
    ("CSC/2023/007", "Ebiere", "Wokoma"), ("CSC/2023/008", "Chinedu", "Okeke"),
    ("CSC/2023/009", "Ngozi", "Harry"), ("CSC/2023/010", "Joseph", "Dike"),
    ("CSC/2023/011", "Kelechi", "Nnadi"), ("CSC/2023/012", "Faith", "Ogbonna"),
]
COURSES = [("CSC 401", "Artificial Intelligence"), ("CSC 411", "Compiler Construction"),
           ("CSC 421", "Computer Security"), ("CSC 431", "Mobile Computing")]


def seed_demo(db, vault, skip_last_student: bool = True, today: date | None = None):
    """Create sample data. The last student is left out so it can be enrolled live through the GUI."""
    rng = np.random.default_rng(2026)
    today = today or date.today()
    db.add_user("STF-014", "Dr. Tonye Jaja", "tjaja@example.org", "Lecturer@2026", "lecturer")
    db.add_user("STF-021", "Mr. Ikenna Obi", "iobi@example.org", "Lecturer@2026", "lecturer")
    n = len(STUDENTS) - (1 if skip_last_student else 0)
    ids = []
    for matric, first, last in STUDENTS[:n]:
        sid = db.add_student(matric, first, last, f"{first.lower()}.{last.lower()}@example.org", "Computer Science", "400")
        base = rng.normal(0, 0.12, 128)
        samples = base + rng.normal(0, 0.01, (config.SAMPLES_REQUIRED, 128))   # synthetic demo vectors
        db.set_template_path(sid, vault.save(matric, samples))
        ids.append(sid)
    course_ids = [db.add_course(code, title, "Computer Science", "400") for code, title in COURSES]
    for cid in course_ids:
        for sid in ids:
            db.enrol(sid, cid, "First", "2026/2027")
    # five past lectures per course, on a fixed weekday each, with individual attendance habits
    habit = rng.uniform(0.86, 1.0, len(ids))
    habit[2], habit[6], habit[9] = 0.5, 0.45, 0.6      # three students who attend irregularly
    lecturer = db.get_user("STF-014")["lecturer_id"]
    for k, cid in enumerate(course_ids):
        d = today - timedelta(days=1 + k)
        weeks = 0
        while weeks < 5:
            if d.weekday() == (k % 5):
                for sid, h in zip(ids, habit):
                    if rng.random() < h:
                        db.mark_attendance(sid, cid, lecturer, datetime(d.year, d.month, d.day, 9, int(rng.integers(0, 25)), int(rng.integers(0, 59))))
                weeks += 1
            d -= timedelta(days=1)
    return ids, course_ids


# ------------------------------------------------------------------ synthetic scene
def _background(w=640, h=480, seed=11):
    rng = np.random.default_rng(seed)
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    top, bot = np.array([186, 198, 207], np.float32), np.array([146, 161, 175], np.float32)
    rgb = (top * (1 - y) + bot * y) * np.ones((1, w, 1), np.float32)
    rgb = np.clip(rgb, 0, 255).astype(np.uint8).copy()
    cv2.rectangle(rgb, (36, 36), (200, 190), (224, 234, 240), -1)           # window
    cv2.rectangle(rgb, (36, 36), (200, 190), (120, 132, 144), 3)
    cv2.line(rgb, (118, 36), (118, 190), (120, 132, 144), 2)
    cv2.line(rgb, (36, 113), (200, 113), (120, 132, 144), 2)
    cv2.rectangle(rgb, (260, 40), (600, 150), (236, 239, 241), -1)          # whiteboard
    cv2.rectangle(rgb, (260, 40), (600, 150), (112, 122, 134), 3)
    cv2.rectangle(rgb, (0, 392), (w, h), (122, 100, 80), -1)                # desk
    cv2.rectangle(rgb, (0, 392), (w, 402), (150, 126, 102), -1)
    rgb = cv2.GaussianBlur(rgb, (0, 0), 1.4)
    return rgb[..., ::-1].copy()                                             # -> BGR


class SyntheticClassroomSource:
    """Draws anonymised silhouettes. `people` entries: {'x','y','s','arrive','student_id','dist'}."""

    def __init__(self, people, name="Simulated feed (demo)"):
        self.people, self.name = people, name
        self.i, self.truth = 0, []
        self._bg = _background()
        self._rng = np.random.default_rng(5)

    def open(self) -> bool:
        self.i = 0
        return True

    def release(self) -> None:
        pass

    def read(self):
        self.i += 1
        frame = self._bg.copy()
        truth = []
        for p in sorted(self.people, key=lambda q: q["y"]):
            if self.i < p["arrive"]:
                continue
            s = p["s"]
            sway = 3.0 * np.sin(self.i / 17.0 + p["x"])
            cx, cy = int(p["x"] + sway), int(p["y"])
            body, light = (82, 66, 52), (104, 86, 70)                        # BGR slate tones
            cv2.ellipse(frame, (cx, cy + int(150 * s)), (int(118 * s), int(96 * s)), 0, 180, 360, body, -1)
            cv2.rectangle(frame, (cx - int(26 * s), cy + int(40 * s)), (cx + int(26 * s), cy + int(78 * s)), body, -1)
            cv2.ellipse(frame, (cx, cy), (int(44 * s), int(56 * s)), 0, 0, 360, body, -1)
            cv2.ellipse(frame, (cx - int(10 * s), cy - int(12 * s)), (int(20 * s), int(26 * s)), 0, 0, 360, light, -1)
            truth.append({"box": (cy - int(60 * s), cx + int(48 * s), cy + int(54 * s), cx - int(48 * s)),
                          "student_id": p["student_id"], "dist": p["dist"]})
        noise = self._rng.normal(0, 2.0, frame.shape).astype(np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        self.truth = truth
        return frame


class ScriptedEngine:
    """Same interface as FaceEngine, but 'recognition' simply reads the scene's ground truth."""

    tolerance = config.TOLERANCE

    def __init__(self, get_source, latency: float = 0.05):
        self._get, self._latency = get_source, latency
        self._names: dict[int, tuple[str, str]] = {}

    def load_gallery(self, entries) -> None:
        self._names = {sid: (matric, name) for sid, matric, name, _enc in entries}

    @property
    def gallery_size(self) -> int:
        return len(self._names)

    def process_frame(self, frame) -> list[Detection]:
        time.sleep(self._latency)
        out = []
        for t in list(self._get().truth):
            sid = t["student_id"]
            if sid in self._names:
                out.append(Detection(box=t["box"], student_id=sid, matric=self._names[sid][0],
                                     name=self._names[sid][1], distance=t["dist"]))
            else:
                out.append(Detection(box=t["box"], distance=t["dist"]))
        return out

    def enrol_sample(self, frame) -> SampleResult:
        truth = list(self._get().truth)
        if len(truth) != 1:
            return SampleResult(False, "No face detected - face the camera directly.")
        rng = np.random.default_rng(int(time.time() * 1000) % 2**32)
        return SampleResult(True, "Sample captured.", encoding=rng.normal(0, 0.12, 128), box=truth[0]["box"])
