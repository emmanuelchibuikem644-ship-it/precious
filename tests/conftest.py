import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["SAFR_DATA_DIR"] = tempfile.mkdtemp(prefix="safr_tests_")

import cv2                      # noqa: E402
import matplotlib               # noqa: E402
import numpy as np              # noqa: E402
import pytest                   # noqa: E402
from skimage import data        # noqa: E402

import config                   # noqa: E402

config.BCRYPT_ROUNDS = 4        # fast hashing in tests only; production uses 12

from core.database import Database      # noqa: E402
from core.face_engine import FaceEngine  # noqa: E402
from core.security import TemplateVault  # noqa: E402


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "test.db")
    yield d
    d.close()


@pytest.fixture
def vault(tmp_path):
    return TemplateVault(tmp_path / "templates", tmp_path / "keys" / "k.key")


@pytest.fixture(scope="session")
def engine():
    return FaceEngine()


def _canvas(img_bgr, w=640, h=480):
    """Place a portrait on a neutral 4:3 canvas, like a webcam frame."""
    ih, iw = img_bgr.shape[:2]
    s = min(w / iw, h / ih)
    img = cv2.resize(img_bgr, (int(iw * s), int(ih * s)))
    canvas = np.full((h, w, 3), 70, np.uint8)
    y0, x0 = (h - img.shape[0]) // 2, (w - img.shape[1]) // 2
    canvas[y0:y0 + img.shape[0], x0:x0 + img.shape[1]] = img
    return canvas


@pytest.fixture(scope="session")
def faces():
    """Two public-domain portrait photographs shipped with Matplotlib and scikit-image,
    used only as controlled test fixtures (never displayed in the application)."""
    hopper = cv2.imread(str(Path(matplotlib.__file__).parent / "mpl-data" / "sample_data" / "grace_hopper.jpg"))
    astro = cv2.cvtColor(data.astronaut(), cv2.COLOR_RGB2BGR)
    eng = FaceEngine(scale=1.0)
    boxes = eng.detect(astro)
    t, r, b, l = max(boxes, key=lambda bx: (bx[2] - bx[0]) * (bx[1] - bx[3]))
    pad = int((b - t) * 0.9)
    astro_face = astro[max(0, t - pad):b + pad, max(0, l - pad):r + pad]
    return {"A": _canvas(hopper), "B": _canvas(astro_face), "canvas": _canvas}
