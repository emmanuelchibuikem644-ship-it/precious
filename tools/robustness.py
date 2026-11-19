"""Controlled robustness experiment on the real recognition pipeline.

One enrolled identity (a public-domain portrait) is probed with the same photograph degraded in ways that
occur in a lecture hall: dim / bright light, blur, noise, compression, head rotation, distance and occlusion.
A second portrait acts as the impostor. This is a single-subject laboratory test, not a population study.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["SAFR_DATA_DIR"] = tempfile.mkdtemp(prefix="safr_rob_")

import cv2                      # noqa: E402
import matplotlib               # noqa: E402
import numpy as np              # noqa: E402
from skimage import data        # noqa: E402

import config                   # noqa: E402
from core.face_engine import FaceEngine   # noqa: E402


def canvas(img, w=640, h=480):
    ih, iw = img.shape[:2]
    s = min(w / iw, h / ih)
    img = cv2.resize(img, (int(iw * s), int(ih * s)))
    c = np.full((h, w, 3), 70, np.uint8)
    y0, x0 = (h - img.shape[0]) // 2, (w - img.shape[1]) // 2
    c[y0:y0 + img.shape[0], x0:x0 + img.shape[1]] = img
    return c


hopper = cv2.imread(str(Path(matplotlib.__file__).parent / "mpl-data" / "sample_data" / "grace_hopper.jpg"))
astro = cv2.cvtColor(data.astronaut(), cv2.COLOR_RGB2BGR)
full = FaceEngine(scale=1.0)
t, r, b, l = max(full.detect(astro), key=lambda bx: (bx[2] - bx[0]) * (bx[1] - bx[3]))
pad = int((b - t) * 0.9)
A, B = canvas(hopper), canvas(astro[max(0, t - pad):b + pad, max(0, l - pad):r + pad])

engine = FaceEngine()
enc = engine.encode(A, engine.detect(A))[0]
engine.load_gallery([(1, "CSC/2023/001", "Enrolled student", np.array([enc]))])
rng = np.random.default_rng(3)


def rotate(f, deg):
    m = cv2.getRotationMatrix2D((320, 240), deg, 1.0)
    return cv2.warpAffine(f, m, (640, 480), borderValue=(70, 70, 70))


def rescale(f, s):
    small = cv2.resize(f, (int(640 * s), int(480 * s)))
    c = np.full((480, 640, 3), 70, np.uint8)
    y0, x0 = (480 - small.shape[0]) // 2, (640 - small.shape[1]) // 2
    c[y0:y0 + small.shape[0], x0:x0 + small.shape[1]] = small
    return c


def jpeg(f, q):
    ok, buf = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, q])
    return cv2.imdecode(buf, 1)


def noise(f, sigma):
    return np.clip(f.astype(np.int16) + rng.normal(0, sigma, f.shape), 0, 255).astype(np.uint8)


def occlude(f):
    t, r, b, l = engine.detect(f)[0]
    g = f.copy()
    cv2.rectangle(g, (l - 5, (t + b) // 2), (r + 5, b + 8), (40, 40, 40), -1)
    return g


cases = [
    ("Enrolment photograph itself", A),
    ("Dim lighting (brightness x0.50)", cv2.convertScaleAbs(A, alpha=0.5)),
    ("Very dim lighting (brightness x0.25)", cv2.convertScaleAbs(A, alpha=0.25)),
    ("Bright lighting (brightness x1.50)", cv2.convertScaleAbs(A, alpha=1.5)),
    ("Low contrast (x0.50)", cv2.convertScaleAbs(A, alpha=0.5, beta=64)),
    ("Out-of-focus (Gaussian blur, sigma 2)", cv2.GaussianBlur(A, (0, 0), 2.0)),
    ("Sensor noise (sigma 15)", noise(A, 15)),
    ("Heavy JPEG compression (quality 20)", jpeg(A, 20)),
    ("Head tilted 10 degrees", rotate(A, 10)),
    ("Head tilted 25 degrees", rotate(A, 25)),
    ("Subject further away (scale 0.85)", rescale(A, 0.85)),
    ("Subject much further away (scale 0.60)", rescale(A, 0.60)),
    ("Lower face covered (mask-like)", occlude(A)),
    ("Different person (impostor)", B),
]
print("=" * 86)
print(f"ROBUSTNESS EXPERIMENT   tolerance = {config.TOLERANCE:.2f}   detection scale = {config.DETECT_SCALE}")
print("=" * 86)
print(f"{'Probe condition':<42}{'Faces':>6}{'Distance':>10}   Decision")
print("-" * 86)
rows = []
for name, frame in cases:
    dets = engine.process_frame(frame)
    if not dets:
        print(f"{name:<42}{0:>6}{'-':>10}   not detected")
        rows.append((name, 0, None, "Not detected"))
        continue
    d = min(dets, key=lambda x: x.distance)
    decision = "Recognised" if d.recognised else "Rejected (unknown)"
    print(f"{name:<42}{len(dets):>6}{d.distance:>10.3f}   {decision}")
    rows.append((name, len(dets), d.distance, decision))
print("=" * 86)
