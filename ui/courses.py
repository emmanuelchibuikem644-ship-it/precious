"""Course set-up and enrolment of students into courses."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import config
from core.database import DuplicateError
from ui.page import Page
from ui.widgets import Card, form_row, make_tree


class CoursesPage(Page):
    def build(self):
        top = ttk.Frame(self)
        top.pack(fill="both", expand=True)
        if self.is_admin:
            left = Card(top, "New course")
            left.pack(side="left", fill="y")
            form = ttk.Frame(left, style="Plain.TFrame")
            form.pack()
            self.f = {k: tk.StringVar() for k in ("code", "title", "level")}
            self.f["dept"] = tk.StringVar(value=config.DEPARTMENT.replace("Department of ", ""))
            form_row(form, 0, "Course code", self.f["code"], 17)
            form_row(form, 1, "Course title", self.f["title"], 17)
            form_row(form, 2, "Level", self.f["level"], 17, values=["100", "200", "300", "400", "500"])
            form_row(form, 3, "Department", self.f["dept"], 17)
            ttk.Button(left, text="Add course", style="Primary.TButton", command=self.add_course).pack(fill="x", pady=(12, 0))
            self.msg = ttk.Label(left, text="", style="Card.TLabel", wraplength=240)
            self.msg.pack(anchor="w", pady=(8, 0))
        right = Card(top, "Courses")
        right.pack(side="left", fill="both", expand=True, padx=(12 if self.is_admin else 0, 0))
        frame, self.tree = make_tree(right, [("c", "Code"), ("t", "Title"), ("l", "Level"), ("n", "Enrolled")],
                                     [74, 200, 52, 72], height=6, anchors={"l": "center", "n": "center"})
        frame.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())
        if not self.is_admin:
            ttk.Label(right, text="Course set-up and enrolment are managed by the Administrator.",
                      style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
            return
        bottom = Card(self, "Enrol students into the selected course")
        bottom.pack(fill="x", pady=(12, 0))
        row = ttk.Frame(bottom, style="Plain.TFrame")
        row.pack(fill="x")
        self.sem, self.ses = tk.StringVar(value="First"), tk.StringVar(value="2026/2027")
        ttk.Label(row, text="Semester", style="Card.TLabel").pack(side="left")
        ttk.Combobox(row, textvariable=self.sem, values=["First", "Second"], width=9, state="readonly").pack(side="left", padx=(6, 16))
        ttk.Label(row, text="Session", style="Card.TLabel").pack(side="left")
        ttk.Entry(row, textvariable=self.ses, width=11).pack(side="left", padx=(6, 16))
        ttk.Button(row, text="Enrol all students at this level", style="Primary.TButton", command=self.enrol_level).pack(side="left")
        self.enrol_msg = ttk.Label(bottom, text="", style="Card.TLabel")
        self.enrol_msg.pack(anchor="w", pady=(8, 0))

    def on_show(self):
        self.refresh()

    def refresh(self):
        sel = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for c in self.app.db.list_courses():
            self.tree.insert("", "end", iid=str(c["course_id"]), values=(c["course_code"], c["course_title"], c["level"], c["enrolled"]))
        if sel and self.tree.exists(sel[0]):
            self.tree.selection_set(sel[0])

    def _on_select(self):
        pass

    def add_course(self):
        v = {k: x.get().strip() for k, x in self.f.items()}
        if not (v["code"] and v["title"] and v["level"]):
            self.msg.configure(text="Course code, title and level are required.", style="Bad.TLabel")
            return
        try:
            self.app.db.add_course(v["code"], v["title"], v["dept"], v["level"])
        except DuplicateError as exc:
            self.msg.configure(text=str(exc), style="Bad.TLabel")
            return
        self.app.db.log(self.app.user["staff_id"], "COURSE_CREATED", v["code"].upper())
        self.msg.configure(text=f"{v['code'].upper()} added.", style="Ok.TLabel")
        for k in ("code", "title", "level"):
            self.f[k].set("")
        self.refresh()

    def enrol_level(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Enrol students", "Select a course in the list first.")
            return
        course = self.app.db.get_course(int(sel[0]))
        added = 0
        for s in self.app.db.list_students():
            if s["level"] == course["level"] and self.app.db.enrol(s["student_id"], course["course_id"], self.sem.get(), self.ses.get().strip()):
                added += 1
        self.app.db.log(self.app.user["staff_id"], "COURSE_ENROLMENT", f"{course['course_code']}: {added} student(s)")
        self.enrol_msg.configure(text=f"{added} student(s) enrolled in {course['course_code']}.", style="Ok.TLabel")
        self.refresh()
