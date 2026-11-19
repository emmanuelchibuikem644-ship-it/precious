import sqlite3
from datetime import datetime, timedelta

import pytest

import config
from core import backup
from core.database import DuplicateError


@pytest.fixture
def world(db):
    admin = db.add_user("ADMIN-01", "Admin", "a@example.org", "Admin1234", "admin")
    lec = db.add_user("STF-014", "Dr Lecturer", "l@example.org", "Lecturer1", "lecturer")
    sids = [db.add_student(f"CSC/2023/{i:03d}", f"First{i}", f"Last{i}", f"s{i}@example.org", "Computer Science", "400")
            for i in range(1, 5)]
    cid = db.add_course("CSC 401", "Artificial Intelligence", "Computer Science", "400")
    for s in sids:
        db.enrol(s, cid, "First", "2026/2027")
    return {"db": db, "admin": admin, "lec": lec, "sids": sids, "cid": cid}


def test_schema_contains_required_tables(db):
    names = {r["name"] for r in db._all("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"students", "courses", "lecturers", "attendance", "enrollments", "audit_log"} <= names


def test_foreign_keys_enforced(world):
    with pytest.raises(sqlite3.IntegrityError):
        world["db"]._exec("INSERT INTO attendance (student_id, course_id, lecturer_id, date, time_in) "
                          "VALUES (999, 1, 1, '2026-01-01', '09:00:00')")


def test_duplicate_matric_rejected(world):
    with pytest.raises(DuplicateError):
        world["db"].add_student("csc/2023/001", "X", "Y", "new@example.org", "CS", "400")


def test_duplicate_email_rejected(world):
    with pytest.raises(DuplicateError):
        world["db"].add_student("CSC/2023/099", "X", "Y", "s1@example.org", "CS", "400")


def test_matric_is_normalised_to_upper_case(world):
    sid = world["db"].add_student("csc/2023/050", "A", "B", "ab@example.org", "CS", "400")
    assert world["db"].get_student(sid)["matric_number"] == "CSC/2023/050"


def test_one_attendance_record_per_student_per_day(world):
    db, w = world["db"], world
    when = datetime(2026, 11, 2, 9, 5)
    assert db.mark_attendance(w["sids"][0], w["cid"], w["lec"], when) is True
    assert db.mark_attendance(w["sids"][0], w["cid"], w["lec"], when + timedelta(minutes=30)) is False
    assert len(db.attendance_rows(w["cid"])) == 1


def test_same_student_can_attend_on_a_new_day(world):
    db, w = world["db"], world
    assert db.mark_attendance(w["sids"][0], w["cid"], w["lec"], datetime(2026, 11, 2, 9, 0))
    assert db.mark_attendance(w["sids"][0], w["cid"], w["lec"], datetime(2026, 11, 9, 9, 0))


def test_deleting_a_student_cascades(world):
    db, w = world["db"], world
    db.mark_attendance(w["sids"][0], w["cid"], w["lec"], datetime(2026, 11, 2, 9, 0))
    db.delete_student(w["sids"][0])
    assert db.attendance_rows(w["cid"]) == [] and w["sids"][0] not in db.enrolled_ids(w["cid"])


def test_sql_injection_text_is_stored_literally(world):
    db = world["db"]
    evil = "Robert'); DROP TABLE students;--"
    sid = db.add_student("CSC/2023/070", evil, "Tables", "bobby@example.org", "CS", "400")
    assert db.get_student(sid)["first_name"] == evil
    assert len(db.list_students()) == 5            # table intact
    assert db.list_students("x' OR '1'='1") == []   # search term is a parameter, not SQL


def test_authentication_success_and_failure(world):
    db = world["db"]
    assert db.authenticate("STF-014", "Lecturer1")["role"] == "lecturer"
    assert db.authenticate("STF-014", "wrong-pass1") is None
    assert db.authenticate("NOBODY", "Lecturer1") is None


def test_login_events_are_audited(world):
    db = world["db"]
    db.authenticate("STF-014", "Lecturer1")
    db.authenticate("STF-014", "bad-pass-1")
    actions = [r["action"] for r in db.audit_entries(10)]
    assert "LOGIN_OK" in actions and "LOGIN_FAILED" in actions


def test_account_locks_after_five_failures(world):
    db = world["db"]
    for _ in range(config.MAX_FAILED_LOGINS):
        assert db.authenticate("STF-014", "bad-pass-1") is None
    assert db.is_locked("STF-014")
    assert db.authenticate("STF-014", "Lecturer1") is None      # correct password still refused while locked
    assert "LOGIN_BLOCKED" in [r["action"] for r in db.audit_entries(5)]


def test_lock_expires_after_window(world):
    db = world["db"]
    for _ in range(config.MAX_FAILED_LOGINS):
        db.authenticate("STF-014", "bad-pass-1")
    db._exec("UPDATE audit_log SET logged_at = datetime('now','localtime','-11 minutes')")
    assert not db.is_locked("STF-014")
    assert db.authenticate("STF-014", "Lecturer1") is not None


def test_user_creation_rules(world):
    db = world["db"]
    with pytest.raises(DuplicateError):
        db.add_user("STF-014", "Other", "o@example.org", "Another123")
    with pytest.raises(ValueError):
        db.add_user("STF-099", "Other", "o2@example.org", "weak")
    with pytest.raises(ValueError):
        db.add_user("STF-098", "Other", "o3@example.org", "Another123", role="student")


def test_course_report_percentages_and_defaulters(world):
    db, w = world["db"], world
    dates = [datetime(2026, 11, d, 9, 0) for d in (2, 9, 16, 23)]
    for i, sid in enumerate(w["sids"]):
        for d in dates[: [4, 3, 2, 1][i]]:
            db.mark_attendance(sid, w["cid"], w["lec"], d)
    rep = db.course_report(w["cid"])
    pct = {r["matric"]: r["percent"] for r in rep["rows"]}
    assert rep["sessions"] == 4
    assert pct == {"CSC/2023/001": 100.0, "CSC/2023/002": 75.0, "CSC/2023/003": 50.0, "CSC/2023/004": 25.0}
    status = {r["matric"]: r["status"] for r in rep["rows"]}
    assert status["CSC/2023/002"] == "Eligible" and status["CSC/2023/003"] == "Defaulter"
    assert rep["defaulters"] == 2 and rep["average"] == 62.5


def test_report_respects_date_range(world):
    db, w = world["db"], world
    for d in (2, 9, 16):
        db.mark_attendance(w["sids"][0], w["cid"], w["lec"], datetime(2026, 11, d, 9, 0))
    rep = db.course_report(w["cid"], "2026-11-09", "2026-11-30")
    assert rep["sessions"] == 2


def test_student_summary(world):
    db, w = world["db"], world
    for d in (2, 9):
        db.mark_attendance(w["sids"][0], w["cid"], w["lec"], datetime(2026, 11, d, 9, 0))
    db.mark_attendance(w["sids"][1], w["cid"], w["lec"], datetime(2026, 11, 2, 9, 0))
    row = db.student_summary(w["sids"][1])[0]
    assert (row["attended"], row["total"], row["percent"]) == (1, 2, 50.0)


def test_dashboard_lists_only_courses_with_lectures(world):
    db, w = world["db"], world
    db.add_course("CSC 411", "Compilers", "Computer Science", "400")
    db.mark_attendance(w["sids"][0], w["cid"], w["lec"], datetime(2026, 11, 2, 9, 0))
    assert [c for c, _ in db.dashboard_stats()["by_course"]] == ["CSC 401"]


def test_enrolment_is_idempotent(world):
    db, w = world["db"], world
    assert db.enrol(w["sids"][0], w["cid"], "First", "2026/2027") is False


def test_backup_is_a_valid_copy(world, tmp_path):
    db = world["db"]
    dest = db.backup_to(tmp_path / "bk")
    copy = sqlite3.connect(dest)
    assert copy.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 4
    copy.close()


def test_daily_backup_runs_once_per_day_and_prunes(world, tmp_path):
    db = world["db"]
    d = tmp_path / "bk"
    assert backup.ensure_daily_backup(db, d) is not None
    assert backup.ensure_daily_backup(db, d) is None
    for i in range(20):
        (d / f"attendance_2020010{i % 10}_{i:06d}.db").write_bytes(b"x")
    removed = backup.prune(d, keep=5)
    assert removed > 0 and len(backup.list_backups(d)) == 5


def test_unknown_staff_id_is_checked_against_a_dummy_hash_of_equal_cost(world):
    from core.database import _DUMMY_HASH
    assert int(_DUMMY_HASH.split("$")[2]) == config.BCRYPT_ROUNDS
