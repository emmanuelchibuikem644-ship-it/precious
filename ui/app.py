"""Main application window: navigation shell, role-based menu and idle time-out."""
from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk

import config
from core import backup
from core.camera import WebcamSource
from core.database import Database
from core.face_engine import FaceEngine
from core.gallery import load_gallery
from core.security import SessionManager, TemplateVault
from ui import theme
from ui.admin import AdminPage
from ui.attendance import AttendancePage
from ui.courses import CoursesPage
from ui.dashboard import DashboardPage
from ui.login import LoginView
from ui.reports_page import ReportsPage
from ui.students import StudentsPage

BOTH = {"admin", "lecturer"}
NAV = [("dashboard", "Dashboard", DashboardPage, BOTH),
       ("students", "Students", StudentsPage, BOTH),
       ("courses", "Courses", CoursesPage, BOTH),
       ("attendance", "Take Attendance", AttendancePage, BOTH),
       ("reports", "Reports", ReportsPage, BOTH),
       ("admin", "Administration", AdminPage, {"admin"})]


class App(tk.Tk):
    def __init__(self, db=None, vault=None, engine=None, source_factory=None, now=datetime.now,
                 geometry="1000x640"):
        super().__init__()
        theme.apply(self)
        self.title(f"{config.APP_TITLE} - {config.INSTITUTION}")
        self.geometry(geometry)
        self.minsize(960, 600)
        self.configure(bg=theme.C["bg"])
        self.db = db or Database()
        self.vault = vault or TemplateVault()
        self.engine = engine or FaceEngine()
        self.source_factory = source_factory or (lambda: WebcamSource(0))
        self.now = now
        self.sessions = SessionManager()
        self.user = self.token = None
        self.pages: dict[str, ttk.Frame] = {}
        self.current: str | None = None
        self.navs: dict[str, tk.Label] = {}
        self.last_backup = backup.ensure_daily_backup(self.db)
        self.reload_gallery()
        self.root_frame = tk.Frame(self, bg=theme.C["bg"])
        self.root_frame.pack(fill="both", expand=True)
        for ev in ("<Any-KeyPress>", "<Any-ButtonPress>", "<Motion>"):
            self.bind_all(ev, lambda e: self.sessions.touch(), add="+")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(1000, self._tick)
        self.show_login()

    # ------------------------------------------------------------ gallery
    def reload_gallery(self) -> int:
        return load_gallery(self.db, self.vault, self.engine)

    # ------------------------------------------------------------- screens
    def _clear(self):
        for w in self.root_frame.winfo_children():
            w.destroy()
        self.pages, self.navs, self.current = {}, {}, None

    def show_login(self, message: str = ""):
        self._clear()
        LoginView(self.root_frame, self, message).pack(fill="both", expand=True)

    def on_login(self, user: dict):
        self.user = user
        self.token = self.sessions.start(user)
        self._build_shell()
        self.show("dashboard")

    def _build_shell(self):
        self._clear()
        C, F = theme.C, theme.FONT
        side = tk.Frame(self.root_frame, bg=C["navy"], width=190)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="SMART\nATTENDANCE", bg=C["navy"], fg="white", font=(F, 14, "bold"), justify="left").pack(anchor="w", padx=20, pady=(22, 4))
        tk.Label(side, text=config.DEPARTMENT, bg=C["navy"], fg="#8FA7C6", font=(F, 8), wraplength=150, justify="left").pack(anchor="w", padx=20, pady=(0, 22))
        for key, label, _cls, roles in NAV:
            if self.user["role"] not in roles:
                continue
            btn = tk.Label(side, text=label, bg=C["navy"], fg="#DCE7F5", font=(F, 11), anchor="w", padx=22, pady=11, cursor="hand2")
            btn.pack(fill="x")
            btn.bind("<Button-1>", lambda e, k=key: self.show(k))
            self.navs[key] = btn
        tk.Frame(side, bg=C["navy"]).pack(fill="both", expand=True)
        tk.Label(side, text="v1.0  \u2022  Prototype", bg=C["navy"], fg="#6F87A8", font=(F, 8)).pack(side="bottom", pady=10)

        right = tk.Frame(self.root_frame, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True)
        head = tk.Frame(right, bg="white", height=54, highlightthickness=1, highlightbackground=C["line"])
        head.pack(fill="x")
        head.pack_propagate(False)
        self.title_var = tk.StringVar()
        tk.Label(head, textvariable=self.title_var, bg="white", fg=C["text"], font=(F, 15, "bold")).pack(side="left", padx=22)
        ttk.Button(head, text="Sign out", style="Secondary.TButton", command=self.logout).pack(side="right", padx=14)
        self.timer_var = tk.StringVar()
        tk.Label(head, textvariable=self.timer_var, bg="white", fg=C["muted"], font=(F, 9)).pack(side="right", padx=(0, 10))
        role = "Administrator" if self.user["role"] == "admin" else "Lecturer"
        tk.Label(head, text=f"{self.user['full_name']}  \u2022  {role}", bg="white", fg=C["text"], font=(F, 10)).pack(side="right", padx=(0, 16))

        self.body = tk.Frame(right, bg=C["bg"])
        self.body.pack(fill="both", expand=True, padx=18, pady=14)
        status = tk.Frame(right, bg=C["head"], height=26)
        status.pack(fill="x", side="bottom")
        status.pack_propagate(False)
        self.status_var = tk.StringVar()
        tk.Label(status, textvariable=self.status_var, bg=C["head"], fg=C["muted"], font=(F, 8)).pack(side="left", padx=14)
        self._update_status()

    def _update_status(self):
        cam = self.source_factory().name
        latest = backup.list_backups()
        last = latest[0].stem.split("_")[1] if latest else "none"
        last = f"{last[:4]}-{last[4:6]}-{last[6:]}" if last != "none" else last
        self.status_var.set(f"Database: {config.DB_PATH.name}   |   Camera: {cam}   |   "
                            f"Face templates loaded: {self.engine.gallery_size}   |   Last backup: {last}")

    def show(self, name: str):
        if not self.sessions.validate(self.token):
            return self.logout(expired=True)
        _key, label, cls, roles = next(n for n in NAV if n[0] == name)
        if self.user["role"] not in roles:
            return
        if self.current in self.pages:
            self.pages[self.current].on_hide()
            self.pages[self.current].pack_forget()
        if name not in self.pages:
            self.pages[name] = cls(self.body, self)
        page = self.pages[name]
        page.pack(fill="both", expand=True)
        page.on_show()
        self.current = name
        self.title_var.set(label)
        for k, btn in self.navs.items():
            btn.configure(bg=theme.C["navy2"] if k == name else theme.C["navy"], fg="white" if k == name else "#DCE7F5")
        self._update_status()

    def logout(self, expired: bool = False):
        for page in self.pages.values():
            page.on_hide()
        if self.user:
            self.db.log(self.user["staff_id"], "SESSION_TIMEOUT" if expired else "LOGOUT", "")
        self.sessions.end()
        self.user = self.token = None
        self.show_login("Your session expired after a period of inactivity." if expired else "")

    def _tick(self):
        if self.sessions.active:
            m, s = divmod(self.sessions.remaining(), 60)
            if hasattr(self, "timer_var"):
                self.timer_var.set(f"Session expires in {m:02d}:{s:02d}")
            if self.sessions.expired():
                self.logout(expired=True)
        self.after(1000, self._tick)

    def on_close(self):
        for page in self.pages.values():
            page.on_hide()
        try:
            self.db.close()
        finally:
            self.destroy()
