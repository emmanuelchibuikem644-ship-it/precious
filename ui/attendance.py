"""Live attendance session: camera preview, background recognition and the running register."""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, ttk

import config
from core.session import AttendanceSession
from core.worker import RecognitionWorker
from ui.page import Page
from ui.widgets import Card, VideoPanel, make_tree, stat_tile
from ui import theme


class AttendancePage(Page):
    def build(self):
        self.session = self.worker = self.source = None
        self.running = False
        self._dets, self._seen, self._n = [], 0, 0
        self._fps, self._last = 0.0, time.perf_counter()
        self.courses: dict[str, int] = {}

        top = Card(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="Course", style="Card.TLabel").pack(side="left")
        self.course_var = tk.StringVar()
        self.course_cb = ttk.Combobox(top, textvariable=self.course_var, state="readonly", width=30)
        self.course_cb.pack(side="left", padx=(8, 14))
        self.start_btn = ttk.Button(top, text="Start session", style="Primary.TButton", command=self.start_session)
        self.start_btn.pack(side="left")
        self.end_btn = ttk.Button(top, text="End session", style="Danger.TButton", command=self.end_session, state="disabled")
        self.end_btn.pack(side="left", padx=8)
        self.chip = ttk.Label(top, text="Idle", style="Muted.TLabel")
        self.chip.pack(side="right")

        mid = ttk.Frame(self)
        mid.pack(fill="both", expand=True, pady=(12, 0))
        left = Card(mid, "Live camera")
        left.pack(side="left")
        self.video = VideoPanel(left, (416, 312))
        self.video.pack()
        self.perf = ttk.Label(left, text="Start a session to begin recognition.", style="Muted.TLabel", wraplength=416, justify="left")
        self.perf.pack(anchor="w", pady=(8, 0))

        right = ttk.Frame(mid)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        tiles = ttk.Frame(right)
        tiles.pack(fill="x")
        self.t_present = stat_tile(tiles, "Present", "0", theme.C["ok"])
        self.t_enrolled = stat_tile(tiles, "Enrolled", "0", theme.C["accent"])
        self.t_unknown = stat_tile(tiles, "Unknown", "0", theme.C["bad"])
        for i, t in enumerate((self.t_present, self.t_enrolled, self.t_unknown)):
            t.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))
            tiles.columnconfigure(i, weight=1, uniform="t")
        card = Card(right, "Recorded this session")
        card.pack(fill="both", expand=True, pady=(10, 0))
        frame, self.tree = make_tree(card, [("t", "Time"), ("n", "Student"), ("d", "Match")], [64, 140, 56], height=10,
                                     anchors={"t": "center", "d": "center"})
        frame.pack(fill="both", expand=True)

    def on_show(self):
        rows = self.app.db.list_courses()
        self.courses = {f"{c['course_code']}  -  {c['course_title']}": c["course_id"] for c in rows}
        self.course_cb.configure(values=list(self.courses))
        if rows and not self.course_var.get():
            self.course_cb.current(0)

    def on_hide(self):
        if self.running:
            self.end_session()

    # --------------------------------------------------------------- session
    def start_session(self):
        cid = self.courses.get(self.course_var.get())
        if not cid:
            messagebox.showinfo("Take attendance", "Choose a course first.")
            return
        if self.app.engine.gallery_size == 0:
            messagebox.showwarning("Take attendance", "No face templates are enrolled yet.")
            return
        self.source = self.app.source_factory()
        if not self.source.open():
            messagebox.showerror("Camera", "No camera could be opened. Check the connection and try again.")
            return
        user = self.app.user
        self.session = AttendanceSession(self.app.db, self.app.engine, cid, user["lecturer_id"], actor=user["staff_id"],
                                         now=self.app.now)
        self.worker = RecognitionWorker(self.app.engine)
        self.worker.start()
        self.tree.delete(*self.tree.get_children())
        self.t_enrolled.value_label.configure(text=str(len(self.session.enrolled)))
        self._refresh_counters()
        self.running, self._dets, self._seen, self._n = True, [], 0, 0
        self.start_btn.configure(state="disabled")
        self.end_btn.configure(state="normal")
        self.course_cb.configure(state="disabled")
        self.chip.configure(text="\u25CF  Session running", style="Ok.TLabel")
        self._tick()

    def _tick(self):
        if not self.running:
            return
        frame = self.source.read()
        if frame is None:
            self.chip.configure(text="Camera stream lost", style="Bad.TLabel")
            return self.end_session()
        self._n += 1
        if self._n % config.PROCESS_EVERY_N == 0:
            self.worker.submit(frame.copy())
        if self.worker.version != self._seen:
            self._seen = self.worker.version
            self._dets, newly = self.session.update(self.worker.take())
            for rec in newly:
                self.tree.insert("", 0, values=(rec["time"], rec["name"], f"{rec['distance']:.2f}"))
            self._refresh_counters()
        self.video.show(frame, self._dets)
        now = time.perf_counter()
        self._fps = 0.9 * self._fps + 0.1 / max(now - self._last, 1e-6)
        self._last = now
        self.perf.configure(text=f"Display {self._fps:4.1f} fps   |   recognition {self.worker.latency_ms:4.0f} ms per frame   |   "
                                 f"tolerance {self.app.engine.tolerance:.2f}   |   confirm {self.session.confirm} frames")
        self.after(30, self._tick)

    def _refresh_counters(self):
        self.t_present.value_label.configure(text=str(len(self.session.marked)))
        self.t_unknown.value_label.configure(text=str(self.session.unknown_events))

    def end_session(self):
        if not self.running:
            return
        self.running = False
        self.worker.stop()
        self.source.release()
        summary = self.session.end()
        self.video.clear("Session closed")
        self.start_btn.configure(state="normal")
        self.end_btn.configure(state="disabled")
        self.course_cb.configure(state="readonly")
        self.chip.configure(text=f"Session closed: {summary['present']} of {summary['enrolled']} present", style="Muted.TLabel")
