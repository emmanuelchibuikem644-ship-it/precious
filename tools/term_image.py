"""Render real command-line output as a clean terminal-style PNG (for the project report)."""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

BG, FG, GREEN, DIM, CYAN, YELLOW = "#0F1720", "#D6DEE8", "#7EE787", "#7D8A99", "#79C0FF", "#E3B341"


def render(lines, path, width=1000, size=15):
    """lines: list of str or list of (text, colour) segments."""
    reg = ImageFont.truetype("DejaVuSansMono.ttf", size)
    bold = ImageFont.truetype("DejaVuSansMono-Bold.ttf", size)
    lh, pad, bar = int(size * 1.5), 18, 34
    h = bar + pad * 2 + lh * len(lines)
    img = Image.new("RGB", (width, h), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, width, bar], fill="#1C2733")
    for i, c in enumerate(("#FF5F56", "#FFBD2E", "#27C93F")):
        d.ellipse([16 + i * 22, 11, 28 + i * 22, 23], fill=c)
    d.text((width // 2 - 40, 8), "Terminal", fill="#8B98A8", font=reg)
    y = bar + pad
    for line in lines:
        segs = [(line, FG)] if isinstance(line, str) else line
        x = pad
        for text, colour in segs:
            font = bold if colour == GREEN and text.startswith("$") else reg
            d.text((x, y), text, fill=colour, font=font)
            x += d.textlength(text, font=font)
        y += lh
    img.save(path)
    return img.size
