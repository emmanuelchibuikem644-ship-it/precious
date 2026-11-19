"""These tests run the REAL dlib models (HOG detector + ResNet-34 encoder)."""
import numpy as np
import pytest

import config
from core.face_engine import FaceEngine


def test_detects_a_face(engine, faces):
    boxes = engine.detect(faces["A"])
    assert len(boxes) == 1
    top, right, bottom, left = boxes[0]
    assert 0 <= top < bottom <= 480 and 0 <= left < right <= 640      # coordinates mapped back to full frame


def test_encoding_is_128_dimensional(engine, faces):
    enc = engine.encode(faces["A"], engine.detect(faces["A"]))
    assert len(enc) == 1 and enc[0].shape == (128,)


def test_same_face_has_near_zero_distance(engine, faces):
    enc = engine.encode(faces["A"], engine.detect(faces["A"]))[0]
    engine.load_gallery([(1, "CSC/2023/001", "Fixture A", np.array([enc]))])
    idx, dist = engine.match(enc)
    assert idx == 0 and dist < 1e-6


def test_different_people_are_further_apart_than_tolerance(engine, faces):
    a = engine.encode(faces["A"], engine.detect(faces["A"]))[0]
    b = engine.encode(faces["B"], engine.detect(faces["B"]))[0]
    assert np.linalg.norm(a - b) > config.TOLERANCE


def test_impostor_is_not_matched(engine, faces):
    a = engine.encode(faces["A"], engine.detect(faces["A"]))[0]
    engine.load_gallery([(1, "CSC/2023/001", "Fixture A", np.array([a]))])
    dets = engine.process_frame(faces["B"])
    assert dets and all(not d.recognised for d in dets)


def test_enrolled_face_is_recognised_in_a_frame(engine, faces):
    a = engine.encode(faces["A"], engine.detect(faces["A"]))[0]
    engine.load_gallery([(7, "CSC/2023/007", "Fixture A", np.array([a]))])
    dets = engine.process_frame(faces["A"])
    assert len(dets) == 1 and dets[0].recognised and dets[0].student_id == 7 and dets[0].distance < config.TOLERANCE


def test_empty_gallery_recognises_nobody(faces):
    eng = FaceEngine()
    dets = eng.process_frame(faces["A"])
    assert dets and not dets[0].recognised


def test_blank_frame_has_no_faces(engine):
    assert engine.process_frame(np.full((480, 640, 3), 90, np.uint8)) == []


def test_enrol_sample_accepts_a_good_frame(engine, faces):
    res = engine.enrol_sample(faces["A"])
    assert res.ok and res.encoding.shape == (128,)


def test_enrol_sample_rejects_empty_frame(engine):
    res = engine.enrol_sample(np.full((480, 640, 3), 90, np.uint8))
    assert not res.ok and "No face" in res.message


def test_enrol_sample_rejects_two_faces(engine, faces):
    import cv2
    two = np.hstack([cv2.resize(faces["A"], (320, 240)), cv2.resize(faces["A"], (320, 240))])
    two = faces["canvas"](two)
    eng = FaceEngine(scale=1.0)
    res = eng.enrol_sample(two)
    assert not res.ok and "More than one" in res.message


def test_enrol_sample_rejects_small_face(engine, faces, monkeypatch):
    monkeypatch.setattr(config, "MIN_FACE_PIXELS", 400)
    res = engine.enrol_sample(faces["A"])
    assert not res.ok and "too small" in res.message
