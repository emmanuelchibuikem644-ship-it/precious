"""Attendance-session logic, exercised with a scripted detector so each rule can be tested in isolation."""
import pytest

import config
from core.face_engine import Detection
from core.session import AttendanceSession


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class Script:
    def __init__(self):
        self.next = []

    def process_frame(self, frame):
        return self.next


def det(sid, name="Student", dist=0.3):
    return Detection(box=(10, 90, 90, 10), student_id=sid, matric=f"M{sid}", name=name, distance=dist)


def unknown():
    return Detection(box=(10, 90, 90, 10), distance=0.8)


@pytest.fixture
def setup(db):
    lec = db.add_user("STF-014", "Dr L", "l@example.org", "Lecturer1")
    sids = [db.add_student(f"CSC/2023/{i:03d}", f"F{i}", f"L{i}", f"s{i}@example.org", "CS", "400") for i in (1, 2, 3)]
    cid = db.add_course("CSC 401", "AI", "CS", "400")
    for s in sids[:2]:
        db.enrol(s, cid, "First", "2026/2027")
    eng, clock = Script(), Clock()
    sess = AttendanceSession(db, eng, cid, lec, "STF-014", clock=clock)
    return db, eng, clock, sess, sids, cid


def test_attendance_needs_consecutive_confirmation(setup):
    db, eng, clock, sess, sids, cid = setup
    eng.next = [det(sids[0])]
    for _ in range(config.CONFIRM_FRAMES - 1):
        assert sess.process(None)[1] == []
    assert len(sess.process(None)[1]) == 1
    assert len(db.attendance_rows(cid)) == 1


def test_a_gap_resets_the_confirmation_counter(setup):
    db, eng, clock, sess, sids, cid = setup
    eng.next = [det(sids[0])]
    sess.process(None); sess.process(None)
    eng.next = []                      # face leaves the frame
    sess.process(None)
    eng.next = [det(sids[0])]
    sess.process(None); sess.process(None)
    assert db.attendance_rows(cid) == []           # only 2 consecutive frames since the gap


def test_repeated_detection_never_duplicates(setup):
    db, eng, clock, sess, sids, cid = setup
    eng.next = [det(sids[0])]
    for _ in range(30):
        sess.process(None)
    assert len(db.attendance_rows(cid)) == 1


def test_student_not_enrolled_in_course_is_not_recorded(setup):
    db, eng, clock, sess, sids, cid = setup
    eng.next = [det(sids[2])]
    for _ in range(6):
        sess.process(None)
    assert db.attendance_rows(cid) == [] and sess.not_enrolled == 6


def test_two_students_recorded_in_the_same_frame(setup):
    db, eng, clock, sess, sids, cid = setup
    eng.next = [det(sids[0]), det(sids[1])]
    for _ in range(config.CONFIRM_FRAMES):
        sess.process(None)
    assert len(db.attendance_rows(cid)) == 2


def test_unknown_faces_are_audited_once_per_interval(setup):
    db, eng, clock, sess, sids, cid = setup
    eng.next = [unknown()]
    for _ in range(10):
        sess.process(None)
    assert sess.unknown_events == 1
    clock.t += config.UNKNOWN_LOG_INTERVAL + 1
    sess.process(None)
    assert sess.unknown_events == 2
    assert len(db.audit_entries(50, "RECOGNITION_FAILED")) == 2


def test_session_start_and_end_are_audited(setup):
    db, eng, clock, sess, sids, cid = setup
    summary = sess.end()
    actions = [r["action"] for r in db.audit_entries(10)]
    assert "SESSION_START" in actions and "SESSION_END" in actions
    assert summary["enrolled"] == 2 and summary["present"] == 0


def test_student_already_present_today_is_not_double_counted(setup):
    db, eng, clock, sess, sids, cid = setup
    db.mark_attendance(sids[0], cid, 1)
    eng.next = [det(sids[0])]
    for _ in range(config.CONFIRM_FRAMES):
        sess.process(None)
    assert len(db.attendance_rows(cid)) == 1
