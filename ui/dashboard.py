"""Dashboard: headline figures, attendance rate per course and the latest records."""
from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk

import config
from ui import theme
from ui.page import Page
from ui.widgets import Card, make_tree, stat_tile


class DashboardPage(Page):
    def build(self):
        C = theme.C
        top = ttk.Frame(self)
        top.pack(fill="x")
        self.tiles = {}
        spec = [("students", "Registered students", C["accent"]), ("courses", "Courses", "#6F42C1"),
                ("today", "Recorded today", C["ok"]), ("average", "Average attendance", C["warn"])]
        for i, (key, label, colour) in enumerate(spec):
            tile = stat_tile(top, label, "0", colour)
            tile.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
            top.columnconfigure(i, weight=1, uniform="tiles")
            self.tiles[key] = tile
        mid = ttk.Frame(self)
        mid.pack(fill="both", expand=True, pady=(12, 0))
        left = Card(mid, "Attendance rate by course")
        left.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(left, bg="white", highlightthickness=0, width=380, height=250)
        self.canvas.pack(fill="both", expand=True)
        ttk.Label(left, text=f"Green: at or above {config.ATTENDANCE_THRESHOLD:.0f}% (exam eligible)   Red: below threshold",
                  style="Muted.TLabel").pack(anchor="w", pady=(6, 0))
        right = Card(mid, "Recent attendance records")
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        frame, self.tree = make_tree(right, [("d", "Date"), ("t", "Time"), ("s", "Student"), ("c", "Course")],
                                     [58, 64, 142, 66], height=9)
        frame.pack(fill="both", expand=True)

    def on_show(self):
        stats = self.app.db.dashboard_stats()
        self.tiles["students"].value_label.configure(text=str(stats["students"]))
        self.tiles["courses"].value_label.configure(text=str(stats["courses"]))
        self.tiles["today"].value_label.configure(text=str(stats["today"]))
        self.tiles["average"].value_label.configure(text=f"{stats['average']:.0f}%")
        self._bars(stats["by_course"])
        self.tree.delete(*self.tree.get_children())
        for r in self.app.db.attendance_rows(limit=9):
            self.tree.insert("", "end", values=(datetime.strptime(r["date"], "%Y-%m-%d").strftime("%d %b"), r["time_in"], r["student"], r["course_code"]))

    def _bars(self, data):
        cv = self.canvas
        cv.delete("all")
        cv.update_idletasks()
        w = max(cv.winfo_width(), 380)
        if not data:
            cv.create_text(w // 2, 100, text="No attendance recorded yet.", fill=theme.C["muted"])
            return
        label_w, right_pad, row_h = 78, 56, 44
        for i, (code, pct) in enumerate(data[:5]):
            y = 16 + i * row_h
            colour = theme.C["ok"] if pct >= config.ATTENDANCE_THRESHOLD else theme.C["bad"]
            cv.create_text(0, y + 12, text=code, anchor="w", fill=theme.C["text"], font=(theme.FONT, 10, "bold"))
            cv.create_rectangle(label_w, y, w - right_pad, y + 24, fill=theme.C["head"], outline="")
            cv.create_rectangle(label_w, y, label_w + (w - right_pad - label_w) * pct / 100, y + 24, fill=colour, outline="")
            cv.create_text(w - right_pad + 8, y + 12, text=f"{pct:.0f}%", anchor="w", fill=theme.C["text"], font=(theme.FONT, 10, "bold"))
