"""Build the two terminal-style evidence figures (project tree, test run) from real output."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.term_image import CYAN, DIM, FG, GREEN, YELLOW, render      # noqa: E402

OUT = sys.argv[1]
raw = open(sys.argv[2]).read().splitlines()
tests = [l for l in raw if "PASSED" in l]
N = len(tests)


def n(p):
    return sum(1 for _ in open(os.path.join(ROOT, p), encoding="utf-8"))


desc = {
    "main.py": "application entry point", "config.py": "all adjustable settings",
    "core/database.py": "SQLite schema, parameterised queries, reports", "core/security.py": "bcrypt, AES-256-GCM vault, sessions",
    "core/face_engine.py": "HOG detection, ResNet embeddings, matching", "core/session.py": "confirmation and duplicate rules",
    "core/worker.py": "background recognition thread", "core/camera.py": "webcam and file frame sources",
    "core/gallery.py": "loads encrypted templates", "core/reports.py": "CSV and PDF export", "core/backup.py": "daily backup, retention",
    "ui/app.py": "window, role-based menu, time-out", "ui/login.py": "sign-in, set-up, student portal",
    "ui/dashboard.py": "summary figures and chart", "ui/students.py": "enrolment and student register",
    "ui/courses.py": "course set-up and enrolment", "ui/attendance.py": "live session screen",
    "ui/reports_page.py": "reports and export", "ui/admin.py": "accounts, audit log, backups",
    "ui/theme.py": "colours and styles", "ui/widgets.py": "cards, tiles, camera panel", "ui/page.py": "base class for screens",
}
L = [[("$ ", GREEN), ("tree SmartAttendance", GREEN)], "SmartAttendance/"]


def row(prefix, name, path=None, extra=""):
    segs = [(prefix + name.ljust(24), FG)]
    if path:
        segs += [(f"{n(path):>4} lines  ", DIM), (desc[path], CYAN)]
    elif extra:
        segs.append((" " * 12 + extra, CYAN))
    return segs


L.append(row("|-- ", "main.py", "main.py")); L.append(row("|-- ", "config.py", "config.py"))
L.append(row("|-- ", "requirements.txt", extra="libraries installed with pip"))
L.append(row("|-- ", "core/", extra="application services and data access"))
for f in ("database", "security", "face_engine", "session", "worker", "camera", "gallery", "reports", "backup"):
    L.append(row("|   |-- ", f + ".py", f"core/{f}.py"))
L.append(row("|-- ", "ui/", extra="Tkinter screens"))
for f in ("app", "login", "dashboard", "students", "courses", "attendance", "reports_page", "admin", "theme", "widgets", "page"):
    L.append(row("|   |-- ", f + ".py", f"ui/{f}.py"))
L.append(row("|-- ", "tests/", extra=f"{N} automated tests (pytest)"))
L.append(row("|-- ", "tools/", extra="benchmark, robustness test, demo harness"))
L.append(row("`-- ", "data/", extra="created automatically on first run"))
for p, e in (("    |-- ", "attendance_system.db|SQLite database"), ("    |-- ", "templates/|AES-256-GCM encrypted face templates"),
             ("    |-- ", "keys/|template.key (256-bit)"), ("    |-- ", "backups/|daily database copies"), ("    `-- ", "exports/|CSV and PDF reports")):
    name, ex = e.split("|")
    L.append(row(p, name, extra=ex))
print(render(L, os.path.join(OUT, "t1_tree.png"), width=1000, size=14))

head = [l for l in raw if l.startswith(("platform", "rootdir"))] + [f"collected {N} items"]
final = [l for l in raw if "passed" in l and "=" in l][-1]
by = {}
for l in tests:
    by.setdefault(l.split("::")[0], []).append(l)
T = [[("$ ", GREEN), ("python -m pytest -v", GREEN)]] + [[(h[:112], DIM)] for h in head]
for mod in dict.fromkeys(l.split("::")[0] for l in tests):
    items = by[mod]
    for l in items[:3]:
        name, rest = l.split(" PASSED")
        T.append([(name.replace("tests/", "")[:84].ljust(86), FG), ("PASSED", GREEN), (rest.strip().rjust(8), DIM)])
    T.append([(f"  ... {len(items) - 3} more tests in {mod.replace('tests/', '')}", YELLOW)])
T.append([(final, GREEN)])
print(render(T, os.path.join(OUT, "t2_pytest.png"), width=1060, size=13))
print({m.replace('tests/', ''): len(v) for m, v in by.items()}, N)
