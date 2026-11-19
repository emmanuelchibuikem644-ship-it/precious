"""Student enrolment (camera capture, consent, encrypted template) and the student register."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np

import config
from core import security
from core.database import DuplicateError
from ui import theme
from ui.page import Page
from ui.widgets import Card, VideoPanel, form_row, make_tree


class StudentsPage(Page):
    def build(self):
        self.source = None
        self.running = False
        self.samples: list[np.ndarray] = []
        self.last_frame = None
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)
        if self.is_admin:
            self.enrol_tab = ttk.Frame(self, padding=(0, 12, 0, 0))
            self.nb.add(self.enrol_tab, text="Enrol student")
            self._build_enrol()
        self.list_tab = ttk.Frame(self, padding=(0, 12, 0, 0))
        self.nb.add(self.list_tab, text="Registered students")
        self._build_list()

    # ----------------------------------------------------------- enrolment
    def _build_enrol(self):
        t = self.enrol_tab
        left = Card(t, "Student details")
        left.pack(side="left", fill="y")
        form = ttk.Frame(left, style="Plain.TFrame")
        form.pack(fill="x")
        self.f = {k: tk.StringVar() for k in ("matric", "first", "last", "email", "dept", "level")}
        self.f["dept"].set(config.DEPARTMENT.replace("Department of ", ""))
        form_row(form, 0, "Matric number", self.f["matric"], 26)
        form_row(form, 1, "First name", self.f["first"], 26)
        form_row(form, 2, "Last name", self.f["last"], 26)
        form_row(form, 3, "E-mail", self.f["email"], 26)
        form_row(form, 4, "Department", self.f["dept"], 26)
        form_row(form, 5, "Level", self.f["level"], 26, values=["100", "200", "300", "400", "500"])
        self.consent = tk.BooleanVar()
        ttk.Checkbutton(left, text="The student has given informed consent\nfor facial data to be captured and stored.",
                        variable=self.consent, style="Card.TCheckbutton").pack(anchor="w", pady=(12, 8))
        self.save_btn = ttk.Button(left, text="Save student", style="Primary.TButton", command=self.save, state="disabled")
        self.save_btn.pack(fill="x")
        self.msg = ttk.Label(left, text="", style="Card.TLabel", wraplength=290)
        self.msg.pack(anchor="w", pady=(8, 0))

        right = Card(t, "Face capture")
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.video = VideoPanel(right, (384, 288))
        self.video.pack()
        bar = ttk.Frame(right, style="Plain.TFrame")
        bar.pack(fill="x", pady=(10, 0))
        self.cam_btn = ttk.Button(bar, text="Start camera", style="Secondary.TButton", command=self.toggle_camera)
        self.cam_btn.pack(side="left")
        self.cap_btn = ttk.Button(bar, text="Capture sample", style="Primary.TButton", command=self.capture, state="disabled")
        self.cap_btn.pack(side="left", padx=8)
        ttk.Button(bar, text="Reset", style="Secondary.TButton", command=self.reset).pack(side="right")
        self.dots = tk.Canvas(right, width=384, height=42, bg="white", highlightthickness=0)
        self.dots.pack(pady=(10, 0))
        self.sample_msg = ttk.Label(right, text=f"Capture {config.SAMPLES_REQUIRED} samples with slight head movement.",
                                    style="Muted.TLabel")
        self.sample_msg.pack(anchor="w")
        self._draw_dots()

    def _draw_dots(self):
        self.dots.delete("all")
        for i in range(config.SAMPLES_REQUIRED):
            x = 3 + i * 77
            done = i < len(self.samples)
            self.dots.create_rectangle(x, 4, x + 68, 36, fill=theme.C["ok"] if done else theme.C["head"], outline="")
            self.dots.create_text(x + 34, 20, text=f"Sample {i + 1}" + (" \u2713" if done else ""),
                                  fill="white" if done else theme.C["muted"], font=(theme.FONT, 9, "bold"))

    def toggle_camera(self):
        if self.running:
            return self.stop_camera()
        self.source = self.app.source_factory()
        if not self.source.open():
            messagebox.showerror("Camera", "No camera could be opened. Check the connection and try again.")
            return
        self.running = True
        self.cam_btn.configure(text="Stop camera")
        self.cap_btn.configure(state="normal")
        self._tick()

    start_camera = toggle_camera

    def stop_camera(self):
        self.running = False
        if self.source:
            self.source.release()
        self.video.clear()
        if hasattr(self, "cam_btn"):
            self.cam_btn.configure(text="Start camera")
            self.cap_btn.configure(state="disabled")

    def _tick(self):
        if not self.running:
            return
        frame = self.source.read()
        if frame is not None:
            self.last_frame = frame
            self.video.show(frame, guide=True)
        self.after(40, self._tick)

    def capture(self):
        if self.last_frame is None or len(self.samples) >= config.SAMPLES_REQUIRED:
            return
        res = self.app.engine.enrol_sample(self.last_frame)
        if res.ok:
            self.samples.append(res.encoding)
            self.sample_msg.configure(text=f"Sample {len(self.samples)} of {config.SAMPLES_REQUIRED} captured.",
                                      style="Ok.TLabel")
        else:
            self.sample_msg.configure(text=res.message, style="Bad.TLabel")
        self._draw_dots()
        self.save_btn.configure(state="normal" if len(self.samples) >= config.SAMPLES_REQUIRED else "disabled")

    def reset(self):
        self.samples.clear()
        self._draw_dots()
        self.save_btn.configure(state="disabled")
        self.sample_msg.configure(text=f"Capture {config.SAMPLES_REQUIRED} samples with slight head movement.", style="Muted.TLabel")

    def save(self):
        v = {k: x.get().strip() for k, x in self.f.items()}
        problems = []
        if not security.valid_matric(v["matric"]):
            problems.append("Enter a valid matriculation number.")
        if not (security.valid_name(v["first"]) and security.valid_name(v["last"])):
            problems.append("Enter the student's first and last names.")
        if v["email"] and not security.valid_email(v["email"]):
            problems.append("Enter a valid e-mail address.")
        if not v["level"]:
            problems.append("Select the student's level.")
        if not self.consent.get():
            problems.append("Consent must be confirmed before biometric data is stored.")
        if len(self.samples) < config.SAMPLES_REQUIRED:
            problems.append("Capture all face samples first.")
        if problems:
            self.msg.configure(text="\n".join(problems), style="Bad.TLabel")
            return
        try:
            sid = self.app.db.add_student(v["matric"], v["first"], v["last"], v["email"], v["dept"], v["level"])
        except DuplicateError as exc:
            self.msg.configure(text=str(exc), style="Bad.TLabel")
            return
        path = self.app.vault.save(v["matric"].upper(), np.array(self.samples))
        self.app.db.set_template_path(sid, path)
        self.app.db.log(self.app.user["staff_id"], "STUDENT_ENROLLED", v["matric"].upper())
        self.app.reload_gallery()
        self.msg.configure(text=f"{v['first']} {v['last']} enrolled successfully.", style="Ok.TLabel")
        for var in self.f.values():
            if var is not self.f["dept"]:
                var.set("")
        self.consent.set(False)
        self.reset()
        self.refresh_list()

    # -------------------------------------------------------------- register
    def _build_list(self):
        t = self.list_tab
        card = Card(t)
        card.pack(fill="both", expand=True)
        bar = ttk.Frame(card, style="Plain.TFrame")
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Search", style="Card.TLabel").pack(side="left")
        self.search = tk.StringVar()
        e = ttk.Entry(bar, textvariable=self.search, width=30)
        e.pack(side="left", padx=8)
        e.bind("<KeyRelease>", lambda ev: self.refresh_list())
        self.count = ttk.Label(bar, text="", style="Muted.TLabel")
        self.count.pack(side="right")
        frame, self.tree = make_tree(card, [("m", "Matric number"), ("n", "Name"), ("l", "Level"), ("d", "Department"),
                                            ("e", "E-mail"), ("t", "Template")],
                                     [104, 140, 46, 118, 205, 80], height=11, anchors={"l": "center", "t": "center"})
        frame.pack(fill="both", expand=True)
        if self.is_admin:
            ttk.Button(card, text="Delete selected student (withdrawal / graduation)", style="Danger.TButton",
                       command=self.delete_selected).pack(anchor="e", pady=(10, 0))

    def refresh_list(self):
        self.tree.delete(*self.tree.get_children())
        rows = self.app.db.list_students(self.search.get())
        for s in rows:
            self.tree.insert("", "end", iid=str(s["student_id"]),
                             values=(s["matric_number"], f"{s['last_name']} {s['first_name']}", s["level"],
                                     s["department"], s["email"] or "", "Encrypted" if s["face_template_path"] else "None"))
        self.count.configure(text=f"{len(rows)} student(s)")

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Delete student", "Select a student in the list first.")
            return
        sid = int(sel[0])
        stu = self.app.db.get_student(sid)
        if messagebox.askyesno("Delete student", f"Permanently delete {stu['first_name']} {stu['last_name']} "
                               f"({stu['matric_number']}), their face template and attendance records?"):
            self.app.vault.delete(self.app.db.delete_student(sid))
            self.app.db.log(self.app.user["staff_id"], "STUDENT_DELETED", stu["matric_number"])
            self.app.reload_gallery()
            self.refresh_list()

    def on_show(self):
        self.refresh_list()

    def on_hide(self):
        if self.is_admin:
            self.stop_camera()
