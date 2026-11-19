"""Integration tests: real dlib recognition + encrypted vault + SQLite + reports working together."""
import numpy as np
import pytest

import config
from core import reports
from core.gallery import load_gallery
from core.session import AttendanceSession


@pytest.fixture
def system(db, vault, engine, faces):
    lec = db.add_user("STF-014", "Dr L", "l@example.org", "Lecturer1")
    sid = db.add_student("CSC/2023/001", "Fixture", "One", "f1@example.org", "CS", "400")
    enc = engine.encode(faces["A"], engine.detect(faces["A"]))[0]
    samples = np.array([enc + np.random.default_rng(i).normal(0, 0.005, 128) for i in range(config.SAMPLES_REQUIRED)])
    db.set_template_path(sid, vault.save("CSC/2023/001", samples))
    cid = db.add_course("CSC 401", "AI", "CS", "400")
    db.enrol(sid, cid, "First", "2026/2027")
    return db, vault, engine, faces, lec, sid, cid


def test_enrol_encrypt_load_recognise_record_report(system):
    db, vault, engine, faces, lec, sid, cid = system
    assert load_gallery(db, vault, engine) == 1
    sess = AttendanceSession(db, engine, cid, lec, "STF-014")
    for _ in range(config.CONFIRM_FRAMES):
        sess.process(faces["A"])
    rows = db.attendance_rows(cid)
    assert len(rows) == 1 and rows[0]["matric_number"] == "CSC/2023/001"
    rep = db.course_report(cid)
    assert rep["rows"][0]["percent"] == 100.0 and rep["defaulters"] == 0


def test_impostor_face_is_never_recorded_and_failure_is_logged(system):
    db, vault, engine, faces, lec, sid, cid = system
    load_gallery(db, vault, engine)
    sess = AttendanceSession(db, engine, cid, lec, "STF-014")
    for _ in range(10):
        sess.process(faces["B"])
    assert db.attendance_rows(cid) == []
    assert len(db.audit_entries(10, "RECOGNITION_FAILED")) == 1


def test_stored_template_contains_no_photograph(system):
    db, vault, engine, faces, lec, sid, cid = system
    path = db.get_student(sid)["face_template_path"]
    raw = open(path, "rb").read()
    assert len(raw) < 20_000                      # 5 x 128 doubles, not an image
    assert raw[:2] not in (b"\xff\xd8", b"\x89P")  # not a JPEG / PNG


def test_tampered_template_is_skipped_and_audited(system):
    db, vault, engine, faces, lec, sid, cid = system
    path = db.get_student(sid)["face_template_path"]
    raw = bytearray(open(path, "rb").read())
    raw[30] ^= 0x01
    open(path, "wb").write(bytes(raw))
    assert load_gallery(db, vault, engine) == 0
    assert db.audit_entries(5, "TEMPLATE_TAMPERED")


def test_deleting_a_student_erases_the_template_file(system):
    db, vault, engine, faces, lec, sid, cid = system
    path = db.delete_student(sid)
    vault.delete(path)
    assert not __import__("os").path.exists(path) and db.list_students() == []


def test_csv_and_pdf_exports(system, tmp_path):
    db, vault, engine, faces, lec, sid, cid = system
    from datetime import datetime
    db.mark_attendance(sid, cid, lec, datetime(2026, 11, 2, 9, 0))
    rep = db.course_report(cid)
    rows = [[r["matric"], r["name"], r["attended"], r["total"], r["percent"], r["status"]] for r in rep["rows"]]
    header = ["Matric number", "Student", "Attended", "Held", "Rate (%)", "Status"]
    csv_path = reports.export_csv(tmp_path / "r.csv", header, rows)
    assert csv_path.read_text(encoding="utf-8-sig").splitlines()[0].startswith("Matric number")
    pdf = reports.export_pdf(tmp_path / "r.pdf", "Attendance Report", [("Course", "CSC 401")], ["S/N"] + header,
                             [[1] + r for r in rows], [("Lectures held", "1")], flag_column=6)
    assert pdf.read_bytes()[:5] == b"%PDF-" and pdf.stat().st_size > 1500
