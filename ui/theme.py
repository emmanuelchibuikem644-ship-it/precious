"""Colour palette and ttk styles shared by every screen."""
from __future__ import annotations

from tkinter import font as tkfont
from tkinter import ttk

C = dict(navy="#10263F", navy2="#1B3A5E", accent="#1E6FD9", accent_dark="#1858AE", bg="#F3F5F8",
         card="#FFFFFF", text="#1C2733", muted="#667385", ok="#1B8A3C", warn="#B26A00", bad="#C62828",
         line="#D8DEE6", soft="#EAF1FB", head="#E9EEF5")

FONT = "TkDefaultFont"


def _family(root) -> str:
    avail = set(tkfont.families(root))
    for name in ("Segoe UI", "Calibri", "Liberation Sans", "Arial", "DejaVu Sans"):
        if name in avail:
            return name
    return "TkDefaultFont"


def apply(root) -> str:
    global FONT
    FONT = fam = _family(root)
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkFixedFont"):
        try:
            tkfont.nametofont(name).configure(family=fam if name != "TkFixedFont" else "DejaVu Sans Mono", size=10)
        except Exception:
            pass
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", font=(fam, 10), background=C["bg"], foreground=C["text"])
    st.configure("TFrame", background=C["bg"])
    st.configure("Card.TFrame", background=C["card"], relief="solid", borderwidth=1, bordercolor=C["line"])
    st.configure("Plain.TFrame", background=C["card"])
    st.configure("TLabel", background=C["bg"], foreground=C["text"])
    st.configure("Card.TLabel", background=C["card"])
    st.configure("CardTitle.TLabel", background=C["card"], font=(fam, 11, "bold"))
    st.configure("Muted.TLabel", background=C["card"], foreground=C["muted"], font=(fam, 9))
    st.configure("MutedBg.TLabel", background=C["bg"], foreground=C["muted"], font=(fam, 9))
    st.configure("H1.TLabel", background=C["bg"], font=(fam, 16, "bold"))
    st.configure("Ok.TLabel", background=C["card"], foreground=C["ok"], font=(fam, 10, "bold"))
    st.configure("Bad.TLabel", background=C["card"], foreground=C["bad"], font=(fam, 10, "bold"))
    st.configure("Warn.TLabel", background=C["card"], foreground=C["warn"], font=(fam, 10, "bold"))
    st.configure("StatNum.TLabel", background=C["card"], font=(fam, 22, "bold"))
    for name, bg, fg, hover in (("Primary", C["accent"], "white", C["accent_dark"]),
                                ("Danger", C["bad"], "white", "#9F1F1F"),
                                ("Secondary", "#E3E9F2", C["text"], "#D3DCE9")):
        st.configure(f"{name}.TButton", background=bg, foreground=fg, borderwidth=0, focusthickness=0,
                     focuscolor=bg, padding=(14, 7), font=(fam, 10, "bold"))
        st.map(f"{name}.TButton", background=[("disabled", "#C9D3E0"), ("active", hover)],
               foreground=[("disabled", "#8795A8")])
    st.configure("TEntry", padding=6, fieldbackground="#FFFFFF", bordercolor=C["line"], lightcolor=C["line"],
                 darkcolor=C["line"])
    st.configure("TCombobox", padding=5, fieldbackground="#FFFFFF", bordercolor=C["line"], arrowsize=14)
    st.map("TCombobox", fieldbackground=[("readonly", "#FFFFFF")])
    st.configure("Card.TCheckbutton", background=C["card"], font=(fam, 9))
    st.configure("Treeview", rowheight=27, background="#FFFFFF", fieldbackground="#FFFFFF", bordercolor=C["line"],
                 font=(fam, 10), borderwidth=1)
    st.configure("Treeview.Heading", background=C["head"], foreground=C["text"], font=(fam, 10, "bold"),
                 relief="flat", padding=(8, 7))
    st.map("Treeview", background=[("selected", "#CFE0FA")], foreground=[("selected", C["text"])])
    st.configure("TNotebook", background=C["bg"], borderwidth=0, tabmargins=(0, 0, 0, 0))
    st.configure("TNotebook.Tab", padding=(18, 8), font=(fam, 10, "bold"), background="#E3E9F2",
                 foreground=C["muted"], borderwidth=0)
    st.map("TNotebook.Tab", background=[("selected", C["card"])], foreground=[("selected", C["accent"])])
    st.configure("Horizontal.TProgressbar", troughcolor=C["head"], background=C["accent"], thickness=8)
    return fam
