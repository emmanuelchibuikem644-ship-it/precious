"""Administration: user accounts, audit trail and backups (administrator only)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import config
from core import backup, security
from core.database import DuplicateError
from ui.page import Page
from ui.widgets import Card, form_row, make_tree


class AdminPage(Page):
    def build(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self.nb = nb
        for attr, text in (("users_tab", "User accounts"), ("audit_tab", "Audit log"), ("backup_tab", "Backup and data protection")):
            tab = ttk.Frame(self, padding=(0, 12, 0, 0))
            setattr(self, attr, tab)
            nb.add(tab, text=text)
        self._build_users()
        self._build_audit()
        self._build_backup()

    # ----------------------------------------------------------------- users
    def _build_users(self):
        t = self.users_tab
        left = Card(t, "Add account")
        left.pack(side="left", fill="y")
        form = ttk.Frame(left, style="Plain.TFrame")
        form.pack()
        self.u = {k: tk.StringVar() for k in ("staff", "name", "email", "role", "pw", "pw2")}
        self.u["role"].set("lecturer")
        form_row(form, 0, "Staff ID", self.u["staff"], 22)
        form_row(form, 1, "Full name", self.u["name"], 22)
        form_row(form, 2, "E-mail", self.u["email"], 22)
        form_row(form, 3, "Role", self.u["role"], 22, values=["lecturer", "admin"])
        form_row(form, 4, "Password", self.u["pw"], 22, show="\u2022")
        form_row(form, 5, "Confirm", self.u["pw2"], 22, show="\u2022")
        ttk.Button(left, text="Create account", style="Primary.TButton", command=self.add_user).pack(fill="x", pady=(12, 0))
        self.umsg = ttk.Label(left, text="Passwords: 8+ characters, letters and digits.", style="Muted.TLabel", wraplength=240)
        self.umsg.pack(anchor="w", pady=(8, 0))
        right = Card(t, "Staff accounts")
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        frame, self.utree = make_tree(right, [("s", "Staff ID"), ("n", "Name"), ("e", "E-mail"), ("r", "Role")],
                                      [70, 130, 150, 62], height=9, anchors={"r": "center"})
        frame.pack(fill="both", expand=True)

    def add_user(self):
        v = {k: x.get().strip() for k, x in self.u.items()}
        v["pw"], v["pw2"] = self.u["pw"].get(), self.u["pw2"].get()
        if not (v["staff"] and v["name"]):
            self.umsg.configure(text="Staff ID and full name are required.", style="Bad.TLabel")
        elif v["email"] and not security.valid_email(v["email"]):
            self.umsg.configure(text="Enter a valid e-mail address.", style="Bad.TLabel")
        elif v["pw"] != v["pw2"]:
            self.umsg.configure(text="The two passwords do not match.", style="Bad.TLabel")
        else:
            try:
                self.app.db.add_user(v["staff"], v["name"], v["email"], v["pw"], v["role"])
            except (ValueError, DuplicateError) as exc:
                self.umsg.configure(text=str(exc), style="Bad.TLabel")
                return
            self.app.db.log(self.app.user["staff_id"], "USER_CREATED", f"{v['staff']} ({v['role']})")
            self.umsg.configure(text=f"Account {v['staff']} created.", style="Ok.TLabel")
            for var in self.u.values():
                var.set("")
            self.u["role"].set("lecturer")
            self.refresh_users()

    def refresh_users(self):
        self.utree.delete(*self.utree.get_children())
        for u in self.app.db.list_users():
            self.utree.insert("", "end", values=(u["staff_id"], u["full_name"], u["email"] or "", u["role"].capitalize()))

    # ----------------------------------------------------------------- audit
    def _build_audit(self):
        card = Card(self.audit_tab)
        card.pack(fill="both", expand=True)
        bar = ttk.Frame(card, style="Plain.TFrame")
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Show", style="Card.TLabel").pack(side="left")
        self.filter = tk.StringVar(value="All events")
        cb = ttk.Combobox(bar, textvariable=self.filter, state="readonly", width=26,
                          values=["All events", "LOGIN_OK", "LOGIN_FAILED", "STUDENT_ENROLLED", "SESSION_START",
                                  "RECOGNITION_FAILED", "REPORT_EXPORTED", "BACKUP"])
        cb.pack(side="left", padx=8)
        cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_audit())
        ttk.Button(bar, text="Refresh", style="Secondary.TButton", command=self.refresh_audit).pack(side="left")
        frame, self.atree = make_tree(card, [("t", "Time"), ("u", "User"), ("a", "Action"), ("d", "Details")],
                                      [134, 78, 178, 300], height=12)
        frame.pack(fill="both", expand=True)

    def refresh_audit(self):
        self.atree.delete(*self.atree.get_children())
        sel = self.filter.get()
        for r in self.app.db.audit_entries(150, None if sel == "All events" else sel):
            self.atree.insert("", "end", values=(r["logged_at"], r["actor"] or "", r["action"], r["details"] or ""))

    # ---------------------------------------------------------------- backup
    def _build_backup(self):
        t = self.backup_tab
        left = Card(t, "Database backup")
        left.pack(side="left", fill="y")
        ttk.Label(left, text=f"A backup is created automatically on the first launch of each day.\n"
                             f"The newest {config.BACKUP_KEEP} copies are kept.", style="Muted.TLabel", wraplength=260,
                  justify="left").pack(anchor="w")
        ttk.Button(left, text="Back up now", style="Primary.TButton", command=self.backup_now).pack(fill="x", pady=(14, 0))
        self.bmsg = ttk.Label(left, text="", style="Card.TLabel", wraplength=260)
        self.bmsg.pack(anchor="w", pady=(8, 0))
        prot = Card(t, "Data protection in force")
        prot.pack(side="left", fill="both", expand=True, padx=(12, 0))
        for line in ("Face templates: AES-256-GCM encrypted files (no photographs stored)",
                     "Passwords: bcrypt hashes with per-user salt",
                     "Database access: parameterised SQL statements only",
                     "Sessions: random token, 30-minute idle time-out",
                     "Lock-out: 5 failed sign-ins block the account for 10 minutes",
                     "Withdrawal / graduation: student record and template can be erased"):
            ttk.Label(prot, text="\u2713  " + line, style="Card.TLabel", wraplength=430, justify="left").pack(anchor="w", pady=3)
        ttk.Label(prot, text="Stored backups", style="CardTitle.TLabel").pack(anchor="w", pady=(14, 4))
        frame, self.btree = make_tree(prot, [("f", "File"), ("s", "Size")], [260, 80], height=4, anchors={"s": "e"})
        frame.pack(fill="x")

    def backup_now(self):
        dest = self.app.db.backup_to(config.BACKUP_DIR)
        backup.prune()
        self.app.db.log(self.app.user["staff_id"], "BACKUP", f"Manual backup -> {dest.name}")
        self.bmsg.configure(text=f"Saved {dest.name}", style="Ok.TLabel")
        self.refresh_backups()

    def refresh_backups(self):
        self.btree.delete(*self.btree.get_children())
        for p in backup.list_backups()[:6]:
            self.btree.insert("", "end", values=(p.name, f"{p.stat().st_size / 1024:.0f} KB"))

    def on_show(self):
        self.refresh_users()
        self.refresh_audit()
        self.refresh_backups()
