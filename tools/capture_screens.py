"""Drives the real GUI (headless X server) through a typical working day and saves a screenshot at each step."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEMO = Path("/home/claude/work/demo_data")
OUT = Path("/home/claude/work/shots")
shutil.rmtree(DEMO, ignore_errors=True)
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True, exist_ok=True)
os.environ["SAFR_DATA_DIR"] = str(DEMO)

import config                                                    # noqa: E402
from PIL import ImageGrab                                        # noqa: E402
from tools.demo_harness import ScriptedEngine, SyntheticClassroomSource, seed_demo   # noqa: E402
from ui.app import App                                           # noqa: E402
from ui.login import StudentPortal                               # noqa: E402

holder = {"src": SyntheticClassroomSource([dict(x=320, y=235, s=1.25, arrive=1, student_id=None, dist=0.0)])}
engine = ScriptedEngine(lambda: holder["src"])
t0 = time.monotonic()
base = datetime.now().replace(hour=9, minute=2, second=0, microsecond=0)
app = App(engine=engine, source_factory=lambda: holder["src"],
          now=lambda: base + timedelta(seconds=(time.monotonic() - t0) * 25), geometry="1000x640+30+30")


def pump(sec=0.3):
    end = time.time() + sec
    while time.time() < end:
        app.update()
        time.sleep(0.01)


def shot(name, widget=None):
    pump(0.3)
    w = widget or app
    x, y, wd, ht = w.winfo_rootx(), w.winfo_rooty(), w.winfo_width(), w.winfo_height()
    try:
        img = ImageGrab.grab(bbox=(x, y, x + wd, y + ht), xdisplay=os.environ.get("DISPLAY"))
    except Exception:
        subprocess.run(["import", "-window", "root", str(OUT / "_full.png")], check=True)
        from PIL import Image
        img = Image.open(OUT / "_full.png").crop((x, y, x + wd, y + ht))
    img.save(OUT / f"{name}.png")
    print("saved", name, img.size)


def login_view():
    return app.root_frame.winfo_children()[0]


def sign_in(staff, pw):
    app.show_login()
    pump(0.2)
    v = login_view()
    v.staff.set(staff)
    v.pw.set(pw)
    v.submit()
    pump(0.4)


# ---- 1. first-run set-up ------------------------------------------------------------
pump(0.5)
shot("01_setup")
v = login_view()
for key, val in {"staff": "ADMIN-01", "name": "Systems Administrator", "email": "admin@example.org",
                 "pw": "Admin@2026", "pw2": "Admin@2026"}.items():
    v.v[key].set(val)
v.create_admin()
pump(0.3)
seed_demo(app.db, app.vault)
app.reload_gallery()

# ---- 2. login screen and student portal ------------------------------------------------
app.show_login()
pump(0.2)
v = login_view()
v.staff.set("ADMIN-01")
v.pw.set("Admin@2026")
shot("02_login")
portal = StudentPortal(app)
portal.geometry("640x470+70+60")
portal.matric.set("CSC/2023/002")
portal.email.set("tamuno.briggs@example.org")
portal.lookup()
pump(0.3)
shot("03_portal", portal)
portal.destroy()

# ---- 3. administrator: enrol a student, set up courses -----------------------------------
v.submit()
pump(0.4)
app.show("students")
page = app.pages["students"]
for k, val in {"matric": "CSC/2023/012", "first": "Faith", "last": "Ogbonna",
               "email": "faith.ogbonna@example.org", "level": "400"}.items():
    page.f[k].set(val)
page.consent.set(True)
page.start_camera()
pump(0.5)
for _ in range(5):
    page.capture()
    pump(0.3)
shot("04_enrol")
page.save()
pump(0.3)
page.nb.select(page.list_tab)
page.refresh_list()
shot("05_students")

app.show("courses")
page = app.pages["courses"]
pump(0.2)
for k, val in {"code": "CSC 441", "title": "Machine Learning", "level": "400"}.items():
    page.f[k].set(val)
page.add_course()
pump(0.2)
new_iid = [i for i in page.tree.get_children() if page.tree.item(i, "values")[0] == "CSC 441"][0]
page.tree.selection_set(new_iid)
page.enrol_level()
pump(0.2)
shot("06_courses")
app.logout()

# ---- 4. lecturer: live attendance, reports, dashboard ------------------------------------
sign_in("STF-014", "Lecturer@2026")
app.show("attendance")
page = app.pages["attendance"]
ids = {m: app.db.get_student_by_matric(m)["student_id"] for m in
       ("CSC/2023/001", "CSC/2023/002", "CSC/2023/004", "CSC/2023/005", "CSC/2023/006", "CSC/2023/008", "CSC/2023/009")}
slots = [(80, 318, .8), (225, 318, .8), (380, 318, .8), (535, 318, .8), (150, 200, .6), (305, 205, .6), (455, 200, .6), (575, 212, .6)]
order = list(ids.values()) + [None]
dists = [0.31, 0.27, 0.35, 0.29, 0.33, 0.38, 0.30, 0.74]
people = [dict(x=x, y=y, s=s, arrive=8 + 14 * i, student_id=sid, dist=d)
          for i, ((x, y, s), sid, d) in enumerate(zip(slots, order, dists))]
holder["src"] = SyntheticClassroomSource(people)
page.course_cb.current(0)
page.start_session()
deadline = time.time() + 40
while time.time() < deadline and (len(page.session.marked) < 7 or holder["src"].i < 125):
    pump(0.2)
pump(0.8)
shot("07_attendance")
page.end_session()
pump(0.3)

app.show("reports")
page = app.pages["reports"]
page.course_cb.current(0)
page.generate()
shot("08_reports")
page.export("csv")
page.export("pdf")
subprocess.run(["pdftoppm", "-r", "110", "-png", "-f", "1", "-l", "1", str(page.exported), str(OUT / "09_report_pdf")], check=True)
print("pdf:", page.exported)

app.show("dashboard")
pump(0.4)
shot("10_dashboard")
app.logout(expired=True)
pump(0.3)
shot("11_timeout")

# ---- 5. administrator: users, audit log, backups -----------------------------------------
sign_in("ADMIN-01", "Admin@2026")
app.show("admin")
page = app.pages["admin"]
pump(0.3)
shot("12_admin_users")
page.nb.select(page.audit_tab)
page.refresh_audit()
shot("13_audit")
page.backup_now()
page.nb.select(page.backup_tab)
pump(0.2)
shot("14_backup")
app.update()
print("done; export dir:", sorted(p.name for p in config.EXPORT_DIR.glob("*")))
app.destroy()
