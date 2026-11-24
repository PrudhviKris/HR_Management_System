import calendar
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.utils.money import amount_in_words, fmt_inr

INDIGO = colors.HexColor("#4f46e5")
LIGHT = colors.HexColor("#eef2ff")
GREY = colors.HexColor("#6b7280")
BORDER = colors.HexColor("#d1d5db")


def render_payslip(slip, company: dict) -> bytes:
    """slip: Payslip ORM row (with adjustments loaded). company: {'name','address'}."""
    buf = BytesIO()
    period = f"{calendar.month_name[slip.payroll_run.month]} {slip.payroll_run.year}"
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
        title=f"Payslip {slip.employee_code} {period}", author=company["name"],
    )
    ss = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=ss["Title"], fontSize=16, textColor=colors.white, alignment=TA_CENTER, spaceAfter=0)
    sub = ParagraphStyle("sub", parent=ss["Normal"], fontSize=9, textColor=colors.white, alignment=TA_CENTER)
    label = ParagraphStyle("label", parent=ss["Normal"], fontSize=8.5, textColor=GREY)
    val = ParagraphStyle("val", parent=ss["Normal"], fontSize=9)
    small = ParagraphStyle("small", parent=ss["Normal"], fontSize=8, textColor=GREY, alignment=TA_CENTER)
    right = ParagraphStyle("right", parent=val, alignment=TA_RIGHT)

    story = []
    header = Table(
        [[Paragraph(company["name"], h)], [Paragraph(company["address"], sub)],
         [Paragraph(f"<b>Salary Slip for {period}</b>", ParagraphStyle("p", parent=sub, fontSize=11))]],
        colWidths=[doc.width],
    )
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), INDIGO), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [header, Spacer(1, 6 * mm)]

    def pair(k, v):
        return [Paragraph(k, label), Paragraph(str(v) if v not in (None, "") else "-", val)]

    doj = slip.date_of_joining.strftime("%d %b %Y") if slip.date_of_joining else "-"
    info = [
        pair("Employee ID", slip.employee_code) + pair("Employee Name", slip.employee_name),
        pair("Department", slip.department_name) + pair("Designation", slip.designation_title),
        pair("Date of Joining", doj) + pair("PAN", slip.pan_number),
        pair("Bank", slip.bank_name) + pair("Account No.", slip.bank_account_masked),
        pair("Working Days", slip.working_days) + pair("Eligible Days", slip.eligible_days),
        pair("Paid Days", f"{slip.paid_days}") + pair("Loss of Pay Days", f"{slip.lop_days}"),
    ]
    w = doc.width
    t = Table(info, colWidths=[w * 0.17, w * 0.33, w * 0.17, w * 0.33])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER), ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f9fafb")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f9fafb")),
    ]))
    story += [t, Spacer(1, 6 * mm)]

    earnings = [
        ("Basic Salary", slip.basic), ("House Rent Allowance", slip.hra),
        ("Conveyance Allowance", slip.conveyance_allowance), ("Medical Allowance", slip.medical_allowance),
        ("Special Allowance", slip.special_allowance),
    ]
    deductions = [
        (f"Loss of Pay ({slip.lop_days} day(s))", slip.lop_deduction), ("Provident Fund", slip.provident_fund),
        ("Professional Tax", slip.professional_tax), ("Income Tax (TDS)", slip.income_tax),
    ]
    for adj in slip.adjustments:
        (earnings if adj.kind.value == "earning" else deductions).append((f"{adj.label} (adj.)", adj.amount))
    earnings = [e for e in earnings if e[1]] or [("-", 0)]
    deductions = [d for d in deductions if d[1]] or [("-", 0)]

    rows = [["Earnings", "Amount (Rs.)", "Deductions", "Amount (Rs.)"]]
    for i in range(max(len(earnings), len(deductions))):
        e = earnings[i] if i < len(earnings) else ("", None)
        d = deductions[i] if i < len(deductions) else ("", None)
        rows.append([
            Paragraph(e[0], val), Paragraph(fmt_inr(e[1]) if e[1] is not None else "", right),
            Paragraph(d[0], val), Paragraph(fmt_inr(d[1]) if d[1] is not None else "", right),
        ])
    rows.append([
        Paragraph("<b>Gross Earnings</b>", val), Paragraph(f"<b>{fmt_inr(slip.gross_earnings)}</b>", right),
        Paragraph("<b>Total Deductions</b>", val), Paragraph(f"<b>{fmt_inr(slip.total_deductions)}</b>", right),
    ])
    et = Table(rows, colWidths=[w * 0.32, w * 0.18, w * 0.32, w * 0.18])
    et.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INDIGO), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"), ("ALIGN", (3, 0), (3, 0), "RIGHT"),
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER), ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDER),
        ("BACKGROUND", (0, -1), (-1, -1), LIGHT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story += [et, Spacer(1, 5 * mm)]

    net = Table(
        [[Paragraph("<b>Net Salary Payable</b>", ParagraphStyle("n", parent=val, fontSize=11)),
          Paragraph(f"<b>Rs. {fmt_inr(slip.net_salary)}</b>", ParagraphStyle("nr", parent=right, fontSize=12))],
         [Paragraph(f"<i>{amount_in_words(slip.net_salary)}</i>", label), ""]],
        colWidths=[w * 0.6, w * 0.4],
    )
    net.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("BOX", (0, 0), (-1, -1), 0.8, INDIGO), ("SPAN", (0, 1), (1, 1)),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [net, Spacer(1, 4 * mm)]

    pay = f"Payment status: {slip.payment_status.value.title()}"
    if slip.transaction_ref:
        pay += f" &middot; Ref: {slip.transaction_ref}"
    if slip.credited_at:
        pay += f" &middot; Credited on {slip.credited_at:%d %b %Y}"
    story += [Paragraph(pay, label), Spacer(1, 10 * mm)]
    story.append(Paragraph(
        "This is a computer-generated salary slip and does not require a signature. "
        f"Loss of Pay = (monthly gross / working days) x LOP days.", small))

    doc.build(story)
    return buf.getvalue()
