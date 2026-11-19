"""CSV and printable PDF attendance reports."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import config


def export_csv(path: str | Path, header: list[str], rows: list[list]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def export_pdf(path: str | Path, title: str, meta: list[tuple[str, str]], header: list[str],
               rows: list[list], summary: list[tuple[str, str]], generated: datetime | None = None,
               flag_column: int | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    generated = generated or datetime.now()
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], fontName="Times-Bold", fontSize=15, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=styles["Normal"], fontName="Times-Roman", fontSize=10.5, alignment=1,
                        textColor=colors.HexColor("#444444"), spaceAfter=10)
    body = ParagraphStyle("b", parent=styles["Normal"], fontName="Times-Roman", fontSize=10)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Times-Roman", 8.5)
        canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawString(2 * cm, 1.2 * cm, f"Generated {generated:%d %B %Y, %H:%M} by the {config.APP_TITLE}")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
        canvas.restoreState()

    story = [Paragraph(config.INSTITUTION.upper(), h1),
             Paragraph(f"{config.DEPARTMENT} &nbsp;|&nbsp; {title}", h2)]
    meta_tbl = Table([[Paragraph(f"<b>{k}</b>", body), Paragraph(v, body)] for k, v in meta],
                     colWidths=[4 * cm, 12 * cm])
    meta_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                                  ("TOPPADDING", (0, 0), (-1, -1), 2)]))
    story += [meta_tbl, Spacer(1, 10)]

    data = [header] + [[str(c) for c in r] for r in rows]
    n = len(header)
    widths = [1.0 * cm] + [(17 * cm - 1.0 * cm) / (n - 1)] * (n - 1)
    if n == 7:
        widths = [0.9 * cm, 3.3 * cm, 4.3 * cm, 2.0 * cm, 1.7 * cm, 2.1 * cm, 2.7 * cm]
    tbl = Table(data, colWidths=widths, repeatRows=1)
    style = [("FONTNAME", (0, 0), (-1, 0), "Times-Bold"), ("FONTNAME", (0, 1), (-1, -1), "Times-Roman"),
             ("FONTSIZE", (0, 0), (-1, -1), 9.5), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3A5F")),
             ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("ALIGN", (0, 0), (-1, -1), "LEFT"),
             ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C2CC")),
             ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6FA")]),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    if flag_column is not None:
        for i, r in enumerate(rows, start=1):
            if str(r[flag_column]).lower() == "defaulter":
                style.append(("TEXTCOLOR", (flag_column, i), (flag_column, i), colors.HexColor("#B71C1C")))
                style.append(("FONTNAME", (flag_column, i), (flag_column, i), "Times-Bold"))
    tbl.setStyle(TableStyle(style))
    story += [tbl, Spacer(1, 12)]
    sum_tbl = Table([[Paragraph(f"<b>{k}</b>", body), Paragraph(v, body)] for k, v in summary],
                    colWidths=[6 * cm, 10 * cm])
    story += [sum_tbl, Spacer(1, 34)]
    sign = Table([["______________________________", "______________________________"],
                  ["Course Lecturer", "Head of Department"]], colWidths=[8.5 * cm, 8.5 * cm])
    sign.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), "Times-Roman"), ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                              ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story.append(sign)
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                      bottomMargin=2 * cm, title=title, author=config.APP_TITLE).build(
        story, onFirstPage=footer, onLaterPages=footer)
    return path
