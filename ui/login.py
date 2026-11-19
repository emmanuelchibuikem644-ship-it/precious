"""Login screen, first-run administrator setup and the read-only student portal."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import config
from core import security
from core.database import DuplicateError
from ui import theme
from ui.widgets import form_row, make_tree


class LoginView(tk.Frame):
    def __init__(self, parent, app, message: str = ""):
        super().__init__(parent, bg=theme.C["card"])
        self.app = app
        C, F = theme.C, theme.FONT
        left = tk.Frame(self, bg=C["navy"], width=400)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(left, text="SMART\nATTENDANCE\nSYSTEM", fg="white", bg=C["navy"], justify="left",
                 font=(F, 27, "bold")).place(x=44, y=84)
        tk.Label(left, text="Face-recognition attendance\nmanagement for lecture halls", fg="#A9BDD6",
                 bg=C["navy"], justify="left", font=(F, 11)).place(x=44, y=250)
        feats = ["Contactless identity verification", "Attendance recorded in real time",
                 "Encrypted biometric templates", "Printable attendance reports"]
        for i, text in enumerate(feats):
            tk.Label(left, text="\u2022  " + text, fg="#DCE7F5", bg=C["navy"], font=(F, 10)).place(x=44, y=330 + i * 28)
        tk.Label(left, text=f"{config.INSTITUTION}\n{config.DEPARTMENT}", fg="#7E95B3", bg=C["navy"],
                 justify="left", font=(F, 9)).place(x=44, y=545)

        right = tk.Frame(self, bg=C["card"])
        right.pack(side="left", fill="both", expand=True)
        self.form = ttk.Frame(right, style="Plain.TFrame")
        self.form.place(relx=0.5, rely=0.47, anchor="center")
        self.msg = ttk.Label(self.form, text=message, style="Bad.TLabel", wraplength=300)
        if app.db.list_users():
            self._build_login()
        else:
            self._build_setup()

    # ---------------------------------------------------------------- login
    def _build_login(self):
        f = self.form
        ttk.Label(f, text="Sign in", style="Card.TLabel", font=(theme.FONT, 20, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(f, text="Use your staff credentials to continue.", style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 16))
        self.staff, self.pw = tk.StringVar(), tk.StringVar()
        self.e_staff = form_row(f, 2, "Staff ID", self.staff, width=28)
        self.e_pw = form_row(f, 3, "Password", self.pw, width=28, show="\u2022")
        ttk.Button(f, text="Sign in", style="Primary.TButton", command=self.submit).grid(row=4, column=0, columnspan=2, sticky="we", pady=(16, 6))
        self.msg.grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Separator(f).grid(row=6, column=0, columnspan=2, sticky="we", pady=14)
        ttk.Label(f, text="Are you a student?", style="Muted.TLabel").grid(row=7, column=0, columnspan=2, sticky="w")
        ttk.Button(f, text="Open student portal (view only)", style="Secondary.TButton",
                   command=lambda: StudentPortal(self.app)).grid(row=8, column=0, columnspan=2, sticky="we", pady=(6, 0))
        self.e_pw.bind("<Return>", lambda e: self.submit())
        self.e_staff.bind("<Return>", lambda e: self.e_pw.focus_set())
        self.e_staff.focus_set()

    def submit(self):
        staff, pw = self.staff.get().strip(), self.pw.get()
        if not staff or not pw:
            self.msg.configure(text="Enter your Staff ID and password.")
            return
        user = self.app.db.authenticate(staff, pw)
        if user:
            self.app.on_login(user)
        elif self.app.db.is_locked(staff):
            self.msg.configure(text=f"Too many failed attempts. Try again in {config.LOCKOUT_MINUTES} minutes.")
        else:
            self.msg.configure(text="Invalid Staff ID or password.")
            self.pw.set("")

    # ---------------------------------------------------------------- setup
    def _build_setup(self):
        f = self.form
        ttk.Label(f, text="First-time setup", style="Card.TLabel", font=(theme.FONT, 20, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(f, text="Create the administrator account.", style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 12))
        self.v = {k: tk.StringVar() for k in ("staff", "name", "email", "pw", "pw2")}
        form_row(f, 2, "Staff ID", self.v["staff"], width=28)
        form_row(f, 3, "Full name", self.v["name"], width=28)
        form_row(f, 4, "E-mail", self.v["email"], width=28)
        form_row(f, 5, "Password", self.v["pw"], width=28, show="\u2022")
        form_row(f, 6, "Confirm", self.v["pw2"], width=28, show="\u2022")
        ttk.Button(f, text="Create administrator", style="Primary.TButton", command=self.create_admin).grid(row=7, column=0, columnspan=2, sticky="we", pady=(14, 6))
        self.msg.grid(row=8, column=0, columnspan=2, sticky="w")

    def create_admin(self):
        v = {k: x.get().strip() for k, x in self.v.items()}
        v["pw"], v["pw2"] = self.v["pw"].get(), self.v["pw2"].get()
        if not (v["staff"] and v["name"]):
            self.msg.configure(text="Staff ID and full name are required.")
        elif v["email"] and not security.valid_email(v["email"]):
            self.msg.configure(text="Enter a valid e-mail address.")
        elif v["pw"] != v["pw2"]:
            self.msg.configure(text="The two passwords do not match.")
        else:
            try:
                self.app.db.add_user(v["staff"], v["name"], v["email"], v["pw"], "admin")
                self.app.db.log(v["staff"], "ADMIN_CREATED", "First-run setup")
                self.app.show_login("Administrator created. Please sign in.")
            except (ValueError, DuplicateError) as exc:
                self.msg.configure(text=str(exc))


class StudentPortal(tk.Toplevel):
    """Read-only view: a student proves identity with matric number + registered e-mail."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Student Portal - view only")
        self.configure(bg=theme.C["card"])
        self.geometry("640x470")
        self.transient(app)
        body = ttk.Frame(self, style="Plain.TFrame", padding=20)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="My attendance", style="Card.TLabel", font=(theme.FONT, 17, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(body, text="Enter your matriculation number and the e-mail address you registered with.",
                  style="Muted.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 12))
        self.matric, self.email = tk.StringVar(), tk.StringVar()
        form_row(body, 2, "Matric number", self.matric, width=30)
        form_row(body, 3, "Registered e-mail", self.email, width=30)
        ttk.Button(body, text="View my attendance", style="Primary.TButton", command=self.lookup).grid(row=2, column=2, rowspan=2, padx=(14, 0), sticky="ns", pady=5)
        self.info = ttk.Label(body, text="", style="Ok.TLabel")
        self.info.grid(row=4, column=0, columnspan=3, sticky="w", pady=(12, 4))
        frame, self.tree = make_tree(body, [("c", "Course"), ("t", "Title"), ("a", "Attended"), ("h", "Held"), ("p", "Rate")],
                                     [80, 220, 70, 60, 70], height=7,
                                     anchors={"a": "center", "h": "center", "p": "center"})
        frame.grid(row=5, column=0, columnspan=3, sticky="nsew")
        body.rowconfigure(5, weight=1)
        body.columnconfigure(1, weight=1)
        self.tree.tag_configure("low", foreground=theme.C["bad"])

    def lookup(self):
        self.tree.delete(*self.tree.get_children())
        stu = self.app.db.get_student_by_matric(self.matric.get())
        if not stu or (stu["email"] or "").lower() != self.email.get().strip().lower():
            self.info.configure(text="No record matches those details.", style="Bad.TLabel")
            return
        self.app.db.log(stu["matric_number"], "PORTAL_VIEW", "Student viewed own attendance")
        self.info.configure(text=f"{stu['first_name']} {stu['last_name']}  \u2022  {stu['matric_number']}", style="Ok.TLabel")
        for r in self.app.db.student_summary(stu["student_id"]):
            tag = ("low",) if r["percent"] < config.ATTENDANCE_THRESHOLD else ()
            self.tree.insert("", "end", values=(r["course"], r["title"], r["attended"], r["total"], f"{r['percent']:.0f}%"), tags=tag)
