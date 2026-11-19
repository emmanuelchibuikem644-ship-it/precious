"""SQLite data layer. Every statement is parameterised (no string building),
foreign keys are enforced and writes are serialised through a lock so the
recognition thread and the GUI thread can share one connection safely."""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

import config
from core import security

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    student_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    matric_number       VARCHAR(20)  NOT NULL UNIQUE,
    first_name          VARCHAR(50)  NOT NULL,
    last_name           VARCHAR(50)  NOT NULL,
    email               VARCHAR(100) UNIQUE,
    department          VARCHAR(100) NOT NULL,
    level               VARCHAR(10)  NOT NULL,
    face_template_path  VARCHAR(255)
);
CREATE TABLE IF NOT EXISTS courses (
    course_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code   VARCHAR(20)  NOT NULL UNIQUE,
    course_title  VARCHAR(200) NOT NULL,
    department    VARCHAR(100) NOT NULL,
    level         VARCHAR(10)  NOT NULL
);
CREATE TABLE IF NOT EXISTS lecturers (
    lecturer_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id       VARCHAR(20)  NOT NULL UNIQUE,
    full_name      VARCHAR(100) NOT NULL,
    email          VARCHAR(100) UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,
    role           VARCHAR(20)  DEFAULT 'lecturer'
);
CREATE TABLE IF NOT EXISTS attendance (
    attendance_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    course_id      INTEGER NOT NULL REFERENCES courses(course_id)   ON DELETE CASCADE,
    lecturer_id    INTEGER NOT NULL REFERENCES lecturers(lecturer_id),
    date           DATE NOT NULL,
    time_in        TIME NOT NULL,
    status         VARCHAR(20) DEFAULT 'Present'
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_attendance_once ON attendance(student_id, course_id, date);
CREATE TABLE IF NOT EXISTS enrollments (
    enrollment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    course_id      INTEGER NOT NULL REFERENCES courses(course_id)   ON DELETE CASCADE,
    semester       VARCHAR(20) NOT NULL,
    session        VARCHAR(20) NOT NULL,
    UNIQUE (student_id, course_id, semester, session)
);
CREATE TABLE IF NOT EXISTS audit_log (
    log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at  DATETIME NOT NULL DEFAULT (datetime('now', 'localtime')),
    actor      VARCHAR(50),
    action     VARCHAR(50) NOT NULL,
    details    VARCHAR(500)
);
"""

# Same cost factor as real hashes, so rejecting an unknown Staff ID takes as long as rejecting a wrong password
_DUMMY_HASH = security.hash_password("dummy-Password-1")


class DuplicateError(Exception):
    """Raised when a unique constraint (matric number, e-mail, course code...) is violated."""


class Database:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or config.DB_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")     # survives sudden power loss
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    # ------------------------------------------------------------ helpers
    def _exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def _all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def _one(self, sql: str, params: tuple = ()) -> dict | None:
        with self._lock:
            row = self.conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    # -------------------------------------------------------------- audit
    def log(self, actor: str | None, action: str, details: str = "") -> None:
        self._exec("INSERT INTO audit_log (actor, action, details) VALUES (?, ?, ?)",
                   (actor, action, details[:500]))

    def audit_entries(self, limit: int = 200, action: str | None = None) -> list[dict]:
        if action:
            return self._all("SELECT * FROM audit_log WHERE action = ? ORDER BY log_id DESC LIMIT ?", (action, limit))
        return self._all("SELECT * FROM audit_log ORDER BY log_id DESC LIMIT ?", (limit,))

    # -------------------------------------------------------------- users
    def add_user(self, staff_id: str, full_name: str, email: str, password: str, role: str = "lecturer") -> int:
        problem = security.password_problem(password)
        if problem:
            raise ValueError(problem)
        if role not in ("admin", "lecturer"):
            raise ValueError("Role must be 'admin' or 'lecturer'.")
        try:
            cur = self._exec(
                "INSERT INTO lecturers (staff_id, full_name, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
                (staff_id.strip(), full_name.strip(), email.strip() or None, security.hash_password(password), role))
        except sqlite3.IntegrityError as exc:
            raise DuplicateError("That Staff ID or e-mail address is already registered.") from exc
        return int(cur.lastrowid)

    def get_user(self, staff_id: str) -> dict | None:
        return self._one("SELECT * FROM lecturers WHERE staff_id = ?", (staff_id.strip(),))

    def list_users(self) -> list[dict]:
        return self._all("SELECT lecturer_id, staff_id, full_name, email, role FROM lecturers ORDER BY role, full_name")

    def is_locked(self, staff_id: str) -> bool:
        """Locked after MAX_FAILED_LOGINS consecutive failures inside the lock-out window."""
        rows = self._all(
            "SELECT action, logged_at FROM audit_log WHERE actor = ? AND action IN ('LOGIN_FAILED','LOGIN_OK') "
            "ORDER BY log_id DESC LIMIT ?", (staff_id, config.MAX_FAILED_LOGINS))
        if len(rows) < config.MAX_FAILED_LOGINS or any(r["action"] != "LOGIN_FAILED" for r in rows):
            return False
        recent = self._one("SELECT datetime('now','localtime', ?) AS cutoff", (f"-{config.LOCKOUT_MINUTES} minutes",))
        return rows[0]["logged_at"] >= recent["cutoff"]

    def authenticate(self, staff_id: str, password: str) -> dict | None:
        if self.is_locked(staff_id):
            self.log(staff_id, "LOGIN_BLOCKED", "Account temporarily locked")
            return None
        user = self.get_user(staff_id)
        ok = security.verify_password(password, user["password_hash"] if user else _DUMMY_HASH)
        if user and ok:
            self.log(staff_id, "LOGIN_OK", "")
            return {k: user[k] for k in ("lecturer_id", "staff_id", "full_name", "email", "role")}
        self.log(staff_id, "LOGIN_FAILED", "Invalid credentials")
        return None

    # ----------------------------------------------------------- students
    def add_student(self, matric: str, first: str, last: str, email: str, department: str,
                    level: str, template_path: str | None = None) -> int:
        try:
            cur = self._exec(
                "INSERT INTO students (matric_number, first_name, last_name, email, department, level, face_template_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (matric.strip().upper(), first.strip(), last.strip(), email.strip() or None,
                 department.strip(), level.strip(), template_path))
        except sqlite3.IntegrityError as exc:
            raise DuplicateError("That matriculation number or e-mail address is already registered.") from exc
        return int(cur.lastrowid)

    def set_template_path(self, student_id: int, path: str | None) -> None:
        self._exec("UPDATE students SET face_template_path = ? WHERE student_id = ?", (path, student_id))

    def get_student(self, student_id: int) -> dict | None:
        return self._one("SELECT * FROM students WHERE student_id = ?", (student_id,))

    def get_student_by_matric(self, matric: str) -> dict | None:
        return self._one("SELECT * FROM students WHERE matric_number = ?", (matric.strip().upper(),))

    def list_students(self, search: str | None = None) -> list[dict]:
        if search:
            like = f"%{search.strip()}%"
            return self._all(
                "SELECT * FROM students WHERE matric_number LIKE ? OR first_name LIKE ? OR last_name LIKE ? "
                "ORDER BY last_name, first_name", (like, like, like))
        return self._all("SELECT * FROM students ORDER BY last_name, first_name")

    def delete_student(self, student_id: int) -> str | None:
        """Remove a student and all dependent rows; returns the template path so the caller can erase the file."""
        row = self.get_student(student_id)
        if not row:
            return None
        self._exec("DELETE FROM students WHERE student_id = ?", (student_id,))
        return row["face_template_path"]

    # ------------------------------------------------------------ courses
    def add_course(self, code: str, title: str, department: str, level: str) -> int:
        try:
            cur = self._exec("INSERT INTO courses (course_code, course_title, department, level) VALUES (?, ?, ?, ?)",
                             (code.strip().upper(), title.strip(), department.strip(), level.strip()))
        except sqlite3.IntegrityError as exc:
            raise DuplicateError("That course code already exists.") from exc
        return int(cur.lastrowid)

    def get_course(self, course_id: int) -> dict | None:
        return self._one("SELECT * FROM courses WHERE course_id = ?", (course_id,))

    def list_courses(self) -> list[dict]:
        return self._all(
            "SELECT c.*, (SELECT COUNT(*) FROM enrollments e WHERE e.course_id = c.course_id) AS enrolled "
            "FROM courses c ORDER BY c.course_code")

    def enrol(self, student_id: int, course_id: int, semester: str, session: str) -> bool:
        try:
            self._exec("INSERT INTO enrollments (student_id, course_id, semester, session) VALUES (?, ?, ?, ?)",
                       (student_id, course_id, semester, session))
            return True
        except sqlite3.IntegrityError:
            return False

    def enrolled_students(self, course_id: int) -> list[dict]:
        return self._all(
            "SELECT s.* FROM students s JOIN enrollments e ON e.student_id = s.student_id "
            "WHERE e.course_id = ? ORDER BY s.last_name, s.first_name", (course_id,))

    def enrolled_ids(self, course_id: int) -> set[int]:
        return {r["student_id"] for r in self._all("SELECT student_id FROM enrollments WHERE course_id = ?", (course_id,))}

    # --------------------------------------------------------- attendance
    def mark_attendance(self, student_id: int, course_id: int, lecturer_id: int,
                        when: datetime | None = None) -> bool:
        """Insert one record per student, per course, per day. Returns False for a duplicate."""
        when = when or datetime.now()
        try:
            self._exec(
                "INSERT INTO attendance (student_id, course_id, lecturer_id, date, time_in, status) "
                "VALUES (?, ?, ?, ?, ?, 'Present')",
                (student_id, course_id, lecturer_id, when.strftime("%Y-%m-%d"), when.strftime("%H:%M:%S")))
            return True
        except sqlite3.IntegrityError:
            return False

    def attendance_rows(self, course_id: int | None = None, date_from: str | None = None,
                        date_to: str | None = None, limit: int | None = None) -> list[dict]:
        sql = ("SELECT a.attendance_id, a.date, a.time_in, a.status, s.matric_number, "
               "s.first_name || ' ' || s.last_name AS student, c.course_code "
               "FROM attendance a JOIN students s ON s.student_id = a.student_id "
               "JOIN courses c ON c.course_id = a.course_id WHERE 1 = 1")
        params: list = []
        if course_id:
            sql += " AND a.course_id = ?"; params.append(course_id)
        if date_from:
            sql += " AND a.date >= ?"; params.append(date_from)
        if date_to:
            sql += " AND a.date <= ?"; params.append(date_to)
        sql += " ORDER BY a.date DESC, a.time_in DESC"
        if limit:
            sql += " LIMIT ?"; params.append(limit)
        return self._all(sql, tuple(params))

    def session_dates(self, course_id: int, date_from: str | None = None, date_to: str | None = None) -> list[str]:
        sql = "SELECT DISTINCT date FROM attendance WHERE course_id = ?"
        params: list = [course_id]
        if date_from:
            sql += " AND date >= ?"; params.append(date_from)
        if date_to:
            sql += " AND date <= ?"; params.append(date_to)
        return [r["date"] for r in self._all(sql + " ORDER BY date", tuple(params))]

    def course_report(self, course_id: int, date_from: str | None = None, date_to: str | None = None,
                      threshold: float | None = None) -> dict:
        """Per-student attendance percentage for a course; a lecture counts as held on any date
        on which at least one student was recorded."""
        threshold = config.ATTENDANCE_THRESHOLD if threshold is None else threshold
        dates = self.session_dates(course_id, date_from, date_to)
        total = len(dates)
        rows = []
        for s in self.enrolled_students(course_id):
            counted = self._one(
                "SELECT COUNT(*) AS n FROM attendance WHERE student_id = ? AND course_id = ? "
                "AND date >= COALESCE(?, '0000-00-00') AND date <= COALESCE(?, '9999-12-31')",
                (s["student_id"], course_id, date_from, date_to))["n"]
            pct = round(100.0 * counted / total, 1) if total else 0.0
            rows.append({"matric": s["matric_number"], "name": f"{s['last_name']} {s['first_name']}",
                         "attended": counted, "total": total, "percent": pct,
                         "status": "Eligible" if pct >= threshold else "Defaulter"})
        avg = round(sum(r["percent"] for r in rows) / len(rows), 1) if rows else 0.0
        return {"sessions": total, "rows": rows, "average": avg,
                "defaulters": sum(1 for r in rows if r["status"] == "Defaulter")}

    def student_summary(self, student_id: int) -> list[dict]:
        out = []
        for c in self._all("SELECT c.course_id, c.course_code, c.course_title FROM courses c "
                           "JOIN enrollments e ON e.course_id = c.course_id WHERE e.student_id = ? "
                           "ORDER BY c.course_code", (student_id,)):
            total = len(self.session_dates(c["course_id"]))
            attended = self._one("SELECT COUNT(*) AS n FROM attendance WHERE student_id = ? AND course_id = ?",
                                 (student_id, c["course_id"]))["n"]
            out.append({"course": c["course_code"], "title": c["course_title"], "attended": attended,
                        "total": total, "percent": round(100.0 * attended / total, 1) if total else 0.0})
        return out

    # ----------------------------------------------------------- dashboard
    def dashboard_stats(self) -> dict:
        today = datetime.now().strftime("%Y-%m-%d")
        courses = self.list_courses()
        pcts = [self.course_report(c["course_id"])["average"] for c in courses
                if self.session_dates(c["course_id"])]
        return {
            "students": self._one("SELECT COUNT(*) AS n FROM students")["n"],
            "courses": len(courses),
            "records": self._one("SELECT COUNT(*) AS n FROM attendance")["n"],
            "today": self._one("SELECT COUNT(*) AS n FROM attendance WHERE date = ?", (today,))["n"],
            "average": round(sum(pcts) / len(pcts), 1) if pcts else 0.0,
            "by_course": [(c["course_code"], self.course_report(c["course_id"])["average"]) for c in courses
                          if self.session_dates(c["course_id"])],
        }

    # -------------------------------------------------------------- backup
    def backup_to(self, directory: str | Path) -> Path:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        dest = directory / f"attendance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        with self._lock:
            target = sqlite3.connect(dest)
            self.conn.backup(target)
            target.close()
        return dest
