"""Small reusable widgets: cards, statistic tiles, camera panel and the detection overlay."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import cv2
from PIL import Image, ImageDraw, ImageFont, ImageTk

from ui import theme


class Card(ttk.Frame):
    def __init__(self, parent, title: str | None = None, padding: int = 14, **kw):
        super().__init__(parent, style="Card.TFrame", padding=padding, **kw)
        if title:
            ttk.Label(self, text=title, style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))


def stat_tile(parent, label: str, value: str, color: str) -> tk.Frame:
    outer = tk.Frame(parent, bg=theme.C["card"], highlightthickness=1, highlightbackground=theme.C["line"])
    tk.Frame(outer, bg=color, width=5).pack(side="left", fill="y")
    inner = tk.Frame(outer, bg=theme.C["card"])
    inner.pack(side="left", fill="both", expand=True, padx=12, pady=10)
    num = tk.Label(inner, text=value, bg=theme.C["card"], fg=theme.C["text"], font=(theme.FONT, 22, "bold"))
    num.pack(anchor="w")
    tk.Label(inner, text=label, bg=theme.C["card"], fg=theme.C["muted"], font=(theme.FONT, 9)).pack(anchor="w")
    outer.value_label = num
    return outer


def form_row(parent, row: int, label: str, var=None, width: int = 26, values=None, readonly=False, show=None):
    ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=5, padx=(0, 10))
    if values is not None:
        w = ttk.Combobox(parent, textvariable=var, values=values, width=width - 2, state="readonly")
    else:
        w = ttk.Entry(parent, textvariable=var, width=width, show=show or "")
        if readonly:
            w.state(["readonly"])
    w.grid(row=row, column=1, sticky="we", pady=5)
    return w


def make_tree(parent, columns, widths, height=8, anchors=None):
    frame = ttk.Frame(parent, style="Plain.TFrame")
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", height=height, selectmode="browse")
    for (key, text), w in zip(columns, widths):
        tree.heading(key, text=text)
        tree.column(key, width=w, anchor=(anchors or {}).get(key, "w"), stretch=True)
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    return frame, tree


# ------------------------------------------------------------------ camera
def _font(size: int):
    for name in ("segoeui.ttf", "arial.ttf", "LiberationSans-Regular.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def render_frame(frame_bgr, size, detections=None, guide=False):
    """Convert a BGR frame to a PhotoImage, drawing recognition boxes or an alignment guide."""
    img = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img)
    font = _font(max(13, img.width // 38))
    for det in detections or []:
        top, right, bottom, left = det.box
        colour = (38, 166, 91) if det.recognised else (221, 75, 57)
        draw.rectangle([left, top, right, bottom], outline=colour, width=3)
        recorded = det.recognised and det.note == "Already recorded"
        label = f"{det.name.split()[0]}  {det.distance:.2f}" if det.recognised else "Unknown"
        pad = 25 if recorded else 8
        tw = draw.textlength(label, font=font)
        draw.rectangle([left, bottom, left + tw + pad + 8, bottom + font.size + 8], fill=colour)
        if recorded:                                   # white tick = attendance already recorded
            mid = bottom + (font.size + 8) / 2
            draw.line([(left + 7, mid), (left + 11, mid + 4), (left + 19, mid - 5)], fill="white", width=2)
        draw.text((left + pad, bottom + 4), label, fill="white", font=font)
        if det.note and not recorded:
            draw.text((left, top - font.size - 6), det.note, fill=(255, 214, 102), font=font)
    if guide:
        w, h = img.size
        draw.ellipse([w * 0.32, h * 0.12, w * 0.68, h * 0.88], outline=(255, 255, 255), width=2)
        draw.text((w * 0.5 - 90, h - 34), "Align the face inside the oval", fill="white", font=font)
    img = img.resize(size, Image.LANCZOS)
    return ImageTk.PhotoImage(img)


class VideoPanel(tk.Label):
    def __init__(self, parent, size=(480, 360)):
        super().__init__(parent, bg="#0B1522", width=size[0], height=size[1], fg="#93A4BC",
                         text="Camera preview", font=(theme.FONT, 11))
        self.size = size
        self._photo = None

    def show(self, frame_bgr, detections=None, guide=False):
        self._photo = render_frame(frame_bgr, self.size, detections, guide)
        self.configure(image=self._photo, text="", width=self.size[0], height=self.size[1])

    def clear(self, text="Camera preview"):
        self._photo = None
        self.configure(image="", text=text)
