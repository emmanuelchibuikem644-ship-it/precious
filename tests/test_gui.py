"""GUI tests drive the real Tkinter application (needs a display; run under xvfb-run on a headless machine)."""
import os
import time

import pytest

pytest.importorskip("tkinter")
if not os.environ.get("DISPLAY"):
    pytest.skip("no display available", allow_module_level=True)

import config                                  # noqa: E402
from core.database import Database             # noqa: E402
from core.security import TemplateVault        # noqa: E402
from tools.demo_harness import ScriptedEngine, SyntheticClassroomSource, seed_demo   # noqa: E402
from ui.app import App                         # noqa: E402


@pytest.fixture
def app(tmp_path):
    holder = {"src": SyntheticClassroomSource([dict(x=320, y=235, s=1.25, arrive=1, student_id=None, dist=0.0)])}
    db = Database(tmp_path / "gui.db")
    vault = TemplateVault(tmp_path / "tpl", tmp_path / "k" / "key")
    db.add_user("ADMIN-01", "Systems Administrator", "admin@example.org", "Admin@2026", "admin")
    seed_demo(db, vault)
    a = App(db=db, vault=vault, engine=ScriptedEngine(lambda: holder["src"], latency=0.01),
            source_factory=lambda: holder["src"], geometry="1000x640+10+10")
    a.holder = holder
    yield a
    try:
        a.destroy()
    except Exception:
        pass


def pump(app, sec=0.3):
    end = time.time() + sec
    while time.time() < end:
        app.update()
        time.sleep(0.01)


def login(app, staff, pw):
    v = app.root_frame.winfo_children()[0]
    v.staff.set(staff)
    v.pw.set(pw)
    v.submit()
    pump(app, 0.2)


def test_valid_login_opens_dashboard(app):
    login(app, "ADMIN-01", "Admin@2026")
    assert app.current == "dashboard" and app.user["role"] == "admin" and app.sessions.active


def test_invalid_login_is_refused(app):
    login(app, "ADMIN-01", "WrongPass1")
    assert app.user is None and "Invalid" in app.root_frame.winfo_children()[0].msg.cget("text")


def test_lecturer_menu_hides_administration(app):
    login(app, "STF-014", "Lecturer@2026")
    assert "admin" not in app.navs and "dashboard" in app.navs
    app.show("admin")                                  # direct call must also be refused
    assert app.current != "admin"


def test_administrator_sees_every_screen(app):
    login(app, "ADMIN-01", "Admin@2026")
    for name in ("dashboard", "students", "courses", "attendance", "reports", "admin"):
        app.show(name)
        pump(app, 0.1)
        assert app.current == name


def test_idle_timeout_signs_the_user_out(app):
    login(app, "ADMIN-01", "Admin@2026")
    app.sessions.timeout = 0
    time.sleep(0.05)
    app._tick()
    pump(app, 0.2)
    assert app.user is None and not app.sessions.active
    assert "expired" in app.root_frame.winfo_children()[0].msg.cget("text")
    assert app.db.audit_entries(3, "SESSION_TIMEOUT")


def test_enrolment_through_the_gui_stores_an_encrypted_template(app):
    login(app, "ADMIN-01", "Admin@2026")
    app.show("students")
    page = app.pages["students"]
    for k, val in {"matric": "CSC/2023/012", "first": "Faith", "last": "Ogbonna", "email": "faith@example.org", "level": "400"}.items():
        page.f[k].set(val)
    page.consent.set(True)
    page.start_camera()
    pump(app, 0.3)
    for _ in range(config.SAMPLES_REQUIRED):
        page.capture()
        pump(app, 0.1)
    assert str(page.save_btn.cget("state")) == "normal"
    page.save()
    stu = app.db.get_student_by_matric("CSC/2023/012")
    assert stu and stu["face_template_path"].endswith(".enc") and os.path.exists(stu["face_template_path"])


def test_enrolment_is_blocked_without_consent(app):
    login(app, "ADMIN-01", "Admin@2026")
    app.show("students")
    page = app.pages["students"]
    for k, val in {"matric": "CSC/2023/013", "first": "No", "last": "Consent", "email": "nc@example.org", "level": "400"}.items():
        page.f[k].set(val)
    page.start_camera()
    pump(app, 0.3)
    for _ in range(config.SAMPLES_REQUIRED):
        page.capture()
    page.save()
    assert app.db.get_student_by_matric("CSC/2023/013") is None


def test_live_session_records_attendance_and_stops_cleanly(app):
    login(app, "STF-014", "Lecturer@2026")
    ids = [app.db.get_student_by_matric(f"CSC/2023/00{i}")["student_id"] for i in (1, 2, 3)]
    people = [dict(x=100 + 150 * i, y=318, s=0.8, arrive=5 + 6 * i, student_id=sid, dist=0.3) for i, sid in enumerate(ids)]
    app.holder["src"] = SyntheticClassroomSource(people)
    app.show("attendance")
    page = app.pages["attendance"]
    page.course_cb.current(0)
    page.start_session()
    deadline = time.time() + 20
    while time.time() < deadline and len(page.session.marked) < 3:
        pump(app, 0.2)
    assert len(page.session.marked) == 3
    page.end_session()
    assert not page.running and len(app.db.attendance_rows(page.session.course_id, limit=10)) >= 3
    assert app.db.audit_entries(5, "SESSION_END")


def test_report_screen_exports_files(app):
    login(app, "STF-014", "Lecturer@2026")
    app.show("reports")
    page = app.pages["reports"]
    page.course_cb.current(0)
    page.generate()
    assert page.report and page.report["sessions"] > 0
    page.export("csv")
    page.export("pdf")
    assert page.exported.suffix == ".pdf" and page.exported.exists()
