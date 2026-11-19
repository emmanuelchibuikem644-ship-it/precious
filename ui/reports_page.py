"""Attendance reports with eligibility flags and CSV / PDF export."""
from __future__ import annotations

import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

import config
from core import reports
from ui import theme
from ui.page import Page
from ui.widgets import Card, make_tree, stat_tile


class ReportsPage(Page):
    def build(self):
        self.report = None
        bar = Card(self, padding=10)
        bar.pack(fill="x")
        self.course_var, self.d_from, self.d_to = tk.StringVar(), tk.StringVar(), tk.StringVar()
        ttk.Label(bar, text="Course", style="Card.TLabel").pack(side="left")
        self.course_cb = ttk.Combobox(bar, textvariable=self.course_var, state="readonly", width=30)
        self.course_cb.pack(side="left", padx=(6, 12))
        ttk.Label(bar, text="From", style="Card.TLabel").pack(side="left")
        ttk.Entry(bar, textvariable=self.d_from, width=11).pack(side="left", padx=(6, 10))
        ttk.Label(bar, text="To", style="Card.TLabel").pack(side="left")
        ttk.Entry(bar, textvariable=self.d_to, width=11).pack(side="left", padx=(6, 12))
        ttk.Button(bar, text="Generate", style="Primary.TButton", command=self.generate).pack(side="left")

        tiles = ttk.Frame(self)
        tiles.pack(fill="x", pady=(12, 0))
        self.t_held = stat_tile(tiles, "Lectures held", "-", theme.C["accent"])
        self.t_avg = stat_tile(tiles, "Average attendance", "-", theme.C["ok"])
        self.t_def = stat_tile(tiles, f"Below {config.ATTENDANCE_THRESHOLD:.0f}% (defaulters)", "-", theme.C["bad"])
        for i, t in enumerate((self.t_held, self.t_avg, self.t_def)):
            t.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
            tiles.columnconfigure(i, weight=1, uniform="r")

        card = Card(self)
        card.pack(fill="both", expand=True, pady=(12, 0))
        frame, self.tree = make_tree(card, [("m", "Matric number"), ("n", "Student"), ("a", "Attended"), ("h", "Held"),
                                            ("p", "Rate"), ("s", "Status")], [130, 210, 80, 60, 70, 100], height=9,
                                     anchors={"a": "center", "h": "center", "p": "center", "s": "center"})
        frame.pack(fill="both", expand=True)
        self.tree.tag_configure("def", foreground=theme.C["bad"])
        foot = ttk.Frame(card, style="Plain.TFrame")
        foot.pack(fill="x", pady=(10, 0))
        self.msg = ttk.Label(foot, text="Choose a course and press Generate.", style="Muted.TLabel")
        self.msg.pack(side="left")
        ttk.Button(foot, text="Export PDF", style="Secondary.TButton", command=lambda: self.export("pdf")).pack(side="right")
        ttk.Button(foot, text="Export CSV", style="Secondary.TButton", command=lambda: self.export("csv")).pack(side="right", padx=8)

    def on_show(self):
        courses = self.app.db.list_courses()
        self.map = {f"{c['course_code']}  -  {c['course_title']}": c for c in courses}
        self.course_cb.configure(values=list(self.map))
        if courses and not self.course_var.get():
            self.course_cb.current(0)
        today = self.app.now()
        if not self.d_to.get():
            self.d_to.set(today.strftime("%Y-%m-%d"))
            self.d_from.set((today - timedelta(days=56)).strftime("%Y-%m-%d"))

    def _dates(self):
        out = []
        for var in (self.d_from, self.d_to):
            try:
                datetime.strptime(var.get().strip(), "%Y-%m-%d")
                out.append(var.get().strip())
            except ValueError:
                self.msg.configure(text="Dates must be written as YYYY-MM-DD.", style="Bad.TLabel")
                return None
        return out

    def generate(self):
        course = self.map.get(self.course_var.get())
        dates = self._dates()
        if not course or not dates:
            return
        self.course, self.range = course, dates
        self.report = self.app.db.course_report(course["course_id"], dates[0], dates[1])
        r = self.report
        self.t_held.value_label.configure(text=str(r["sessions"]))
        self.t_avg.value_label.configure(text=f"{r['average']:.0f}%")
        self.t_def.value_label.configure(text=str(r["defaulters"]))
        self.tree.delete(*self.tree.get_children())
        for row in r["rows"]:
            self.tree.insert("", "end", values=(row["matric"], row["name"], row["attended"], row["total"],
                                                f"{row['percent']:.0f}%", row["status"]),
                             tags=("def",) if row["status"] == "Defaulter" else ())
        self.msg.configure(text=f"{len(r['rows'])} student(s) listed for {course['course_code']}.", style="Muted.TLabel")
        self.app.db.log(self.app.user["staff_id"], "REPORT_GENERATED", course["course_code"])

    def export(self, kind: str):
        if not self.report:
            self.msg.configure(text="Generate a report first.", style="Bad.TLabel")
            return
        stem = f"attendance_{self.course['course_code'].replace(' ', '')}_{self.range[0]}_{self.range[1]}"
        rows = [[r["matric"], r["name"], r["attended"], r["total"], f"{r['percent']:.1f}", r["status"]] for r in self.report["rows"]]
        header = ["Matric number", "Student", "Attended", "Held", "Rate (%)", "Status"]
        if kind == "csv":
            path = reports.export_csv(config.EXPORT_DIR / f"{stem}.csv", header, rows)
        else:
            meta = [("Course", f"{self.course['course_code']} - {self.course['course_title']}"),
                    ("Period", f"{self.range[0]} to {self.range[1]}"), ("Prepared by", self.app.user["full_name"])]
            summary = [("Lectures held", str(self.report["sessions"])),
                       ("Average attendance", f"{self.report['average']:.1f}%"),
                       (f"Students below {config.ATTENDANCE_THRESHOLD:.0f}%", str(self.report["defaulters"]))]
            path = reports.export_pdf(config.EXPORT_DIR / f"{stem}.pdf", "Attendance Report", meta,
                                      ["S/N"] + header, [[i] + r for i, r in enumerate(rows, 1)], summary,
                                      generated=self.app.now(), flag_column=6)
        self.app.db.log(self.app.user["staff_id"], "REPORT_EXPORTED", path.name)
        self.msg.configure(text=f"Saved: {path.name}", style="Ok.TLabel")
        self.exported = path
