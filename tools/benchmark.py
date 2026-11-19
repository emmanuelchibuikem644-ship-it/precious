"""Performance benchmark of the real recognition pipeline, data layer and security services."""
from __future__ import annotations

import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["SAFR_DATA_DIR"] = tempfile.mkdtemp(prefix="safr_bench_")

import cv2                      # noqa: E402
import dlib                     # noqa: E402
import matplotlib               # noqa: E402
import numpy as np              # noqa: E402

import config                   # noqa: E402
from core import security       # noqa: E402
from core.database import Database      # noqa: E402
from core.face_engine import FaceEngine  # noqa: E402
from core.security import TemplateVault  # noqa: E402


def ms(fn, n):
    out = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t) * 1000)
    return out


def stat(label, xs, unit="ms"):
    xs = sorted(xs)
    p95 = xs[int(0.95 * (len(xs) - 1))]
    med = statistics.median(xs)
    print(f"  {label:<46} median {med:8.2f} {unit}   mean {statistics.mean(xs):8.2f} {unit}   p95 {p95:8.2f} {unit}   (n={len(xs)})")
    return med


def cpu_name():
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def ram_gb():
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemTotal"):
                return int(line.split()[1]) / 1024 / 1024
    except OSError:
        return 0.0


print("=" * 78)
print("SMART ATTENDANCE SYSTEM - PERFORMANCE BENCHMARK")
print("=" * 78)
print(f"Processor : {cpu_name()} ({os.cpu_count()} logical CPU)")
print(f"Memory    : {ram_gb():.1f} GB          OS: {platform.system()} {platform.release()}")
print(f"Software  : Python {platform.python_version()} | OpenCV {cv2.__version__} | dlib {dlib.__version__} | NumPy {np.__version__}")
print("GPU       : none (CPU-only inference)")

hopper = cv2.imread(str(Path(matplotlib.__file__).parent / "mpl-data" / "sample_data" / "grace_hopper.jpg"))
h, w = hopper.shape[:2]
s = min(640 / w, 480 / h)
img = cv2.resize(hopper, (int(w * s), int(h * s)))
frame = np.full((480, 640, 3), 70, np.uint8)
y0, x0 = (480 - img.shape[0]) // 2, (640 - img.shape[1]) // 2
frame[y0:y0 + img.shape[0], x0:x0 + img.shape[1]] = img

print("\n[1] Recognition pipeline (640 x 480 frame, one face)")
full, half = FaceEngine(scale=1.0), FaceEngine(scale=0.5)
full.detect(frame); half.detect(frame)                            # warm-up
d_full = stat("HOG face detection, full resolution", ms(lambda: full.detect(frame), 30))
d_half = stat("HOG face detection, 0.5x downscale (used)", ms(lambda: half.detect(frame), 30))
boxes = half.detect(frame)
e_ms = stat("ResNet-34 embedding of one face", ms(lambda: half.encode(frame, boxes), 30))
enc = half.encode(frame, boxes)[0]
rng = np.random.default_rng(1)
gallery = [(i, f"M{i}", f"S{i}", rng.normal(0, .12, (5, 128))) for i in range(50)] + [(999, "REAL", "Fixture", np.array([enc]))]
half.load_gallery(gallery)
tot = stat("End-to-end process_frame (gallery of 51 students)", ms(lambda: half.process_frame(frame), 30))
print(f"  -> sustained recognition rate on this machine: {1000 / tot:.1f} frames per second")
print(f"  -> detection speed-up from 0.5x downscaling : {d_full / d_half:.1f}x")

print("\n[2] Matching time against the enrolled gallery (5 templates per student)")
for n in (10, 100, 1000, 5000):
    e = FaceEngine()
    e.load_gallery([(i, f"M{i}", f"S{i}", rng.normal(0, .12, (5, 128))) for i in range(n)])
    q = rng.normal(0, .12, 128)
    stat(f"match against {n:>5} enrolled students", ms(lambda: e.match(q), 300), "ms")

print("\n[3] Database (SQLite, WAL mode)")
db = Database(Path(os.environ["SAFR_DATA_DIR"]) / "bench.db")
lec = db.add_user("STF-001", "Bench", "b@example.org", "Bench12345")
sids = [db.add_student(f"CSC/2023/{i:04d}", "A", "B", f"s{i}@example.org", "CS", "400") for i in range(200)]
cid = db.add_course("CSC 401", "AI", "CS", "400")
for sid in sids:
    db.enrol(sid, cid, "First", "2026/2027")
from datetime import datetime, timedelta
t0 = datetime(2026, 9, 1, 9, 0)
it = iter([(sid, t0 + timedelta(days=7 * k)) for k in range(10) for sid in sids])
stat("INSERT attendance record (committed)", ms(lambda: db.mark_attendance(*(lambda p: (p[0], cid, lec, p[1]))(next(it))), 1000))
stat("Course report: 200 students x 10 lectures", ms(lambda: db.course_report(cid), 10))
stat("Recent-records query (limit 9)", ms(lambda: db.attendance_rows(limit=9), 100))

print("\n[4] Security services")
v = TemplateVault(Path(os.environ["SAFR_DATA_DIR"]) / "t", Path(os.environ["SAFR_DATA_DIR"]) / "k" / "key")
arr = rng.normal(size=(5, 128))
stat("AES-256-GCM seal + open of one template", ms(lambda: v.open(v.seal(arr)), 300))
stat(f"bcrypt hash, cost factor {config.BCRYPT_ROUNDS} (login)", ms(lambda: security.hash_password("Benchmark1"), 5))
print("=" * 78)
