import csv
import io
from datetime import date, datetime
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, Decimal):
        return f"{v:.0f}" if v == v.to_integral() and abs(v) < 1000 else f"{v:.2f}"
    if isinstance(v, float):
        return f"{v:.2f}".rstrip("0").rstrip(".") if v != int(v) else str(int(v))
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, date):
        return v.isoformat()
    if hasattr(v, "value"):
        return str(v.value)
    return str(v)


def _safe_csv(s: str) -> str:
    # neutralise spreadsheet formula injection
    return "'" + s if s and s[0] in "=+-@\t\r" and not _is_number(s) else s


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def to_csv(report: dict) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    cols = report["columns"]
    w.writerow([c["label"] for c in cols])
    for row in report["rows"]:
        w.writerow([_safe_csv(_cell(row.get(c["key"]))) for c in cols])
    if report.get("totals"):
        w.writerow([_safe_csv(_cell(report["totals"].get(c["key"], "Total" if i == 0 else ""))) for i, c in enumerate(cols)])
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM so Excel opens UTF-8 correctly


def to_pdf(report: dict, company_name: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm, title=report["title"])
    ss = getSampleStyleSheet()
    cell = ParagraphStyle("c", parent=ss["Normal"], fontSize=7.5, leading=9)
    head = ParagraphStyle("h", parent=cell, textColor=colors.white, fontName="Helvetica-Bold")
    story = [
        Paragraph(f"<b>{company_name}</b>", ss["Heading2"]),
        Paragraph(report["title"], ss["Heading3"]),
        Paragraph(" &middot; ".join(f"{k}: {v}" for k, v in report.get("filters", {}).items() if v not in (None, "")) or "All records",
                  ParagraphStyle("f", parent=cell, textColor=colors.HexColor("#6b7280"))),
        Spacer(1, 4 * mm),
    ]
    cols = report["columns"]
    data = [[Paragraph(c["label"], head) for c in cols]]
    for row in report["rows"]:
        data.append([Paragraph(_cell(row.get(c["key"])), cell) for c in cols])
    if report.get("totals"):
        data.append([Paragraph(f"<b>{_cell(report['totals'].get(c['key'], 'Total' if i == 0 else ''))}</b>", cell) for i, c in enumerate(cols)])
    if len(data) == 1:
        data.append([Paragraph("No records for the selected filters", cell)] + [""] * (len(cols) - 1))
    t = Table(data, repeatRows=1, colWidths=[doc.width / len(cols)] * len(cols))
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
    ]
    if report.get("totals"):
        style.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eef2ff")))
    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(f"Generated {datetime.now():%d %b %Y %H:%M} &middot; {len(report['rows'])} row(s)",
                           ParagraphStyle("g", parent=cell, textColor=colors.HexColor("#6b7280"))))
    doc.build(story)
    return buf.getvalue()
