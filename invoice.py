# modules/invoice.py
import os
from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


# =========================================================
# Helpers
# =========================================================
def _fmt_idr(n: int) -> str:
    try:
        n = int(round(float(n)))
    except Exception:
        n = 0
    return f"{n:,}".replace(",", ".")

def _safe_str(x) -> str:
    return "" if x is None else str(x)

def _draw_polygon(c: canvas.Canvas, points, fill_color=colors.black, stroke_color=None, stroke=0):
    """
    points: [(x1,y1),(x2,y2),...]
    """
    p = c.beginPath()
    p.moveTo(points[0][0], points[0][1])
    for x, y in points[1:]:
        p.lineTo(x, y)
    p.close()

    if fill_color is not None:
        c.setFillColor(fill_color)
    if stroke_color is not None:
        c.setStrokeColor(stroke_color)
    c.drawPath(p, fill=1, stroke=stroke)

def _try_draw_logo(c: canvas.Canvas, x, y, w, h, logo_path: str):
    """
    Draw logo image if exists; otherwise draw ORBIT text.
    (x,y) is bottom-left.
    """
    if logo_path and os.path.exists(logo_path):
        try:
            img = ImageReader(logo_path)
            iw, ih = img.getSize()
            aspect = ih / float(iw)
            # fit inside w,h
            draw_w = w
            draw_h = draw_w * aspect
            if draw_h > h:
                draw_h = h
                draw_w = draw_h / aspect
            cx = x + (w - draw_w) / 2
            cy = y + (h - draw_h) / 2
            c.drawImage(img, cx, cy, width=draw_w, height=draw_h, mask="auto")
            return
        except Exception:
            pass

    # fallback: simple ORBIT mark
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(x + w / 2, y + h / 2 - 5, "ORBIT")


# =========================================================
# Main: Generate PDF
# meta: dict
# items: list[dict] each item keys:
#   Description, Qty, Price, Total, Details (optional)
# grand_total: int
# =========================================================
def generate_pdf_bytes(meta: dict, items: list, grand_total: int) -> BytesIO:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    # -------------------------
    # Palette / constants
    # -------------------------
    BLACK = colors.HexColor("#0b0b0c")
    GRAY = colors.HexColor("#6e6e73")
    LIGHT = colors.HexColor("#f4f5f7")
    LINE = colors.HexColor("#1b1b1c")  # grid border (dark)
    WHITE = colors.white

    margin = 18 * mm
    top_bar_h = 28 * mm

    logo_block_w = 58 * mm
    logo_block_h = top_bar_h
    ribbon_drop = 18 * mm  # diagonal tail height

    # paths
    LOGO_PATH = meta.get("logo_path", "assets/logo.png")

    # meta fields (safe defaults)
    inv_no = _safe_str(meta.get("inv_no", meta.get("invoice_no", "0001")))
    client = _safe_str(meta.get("client_name", meta.get("client", "-")))
    inv_date = meta.get("date") or meta.get("issued") or datetime.today().strftime("%d / %m / %Y")

    subtotal = meta.get("subtotal", grand_total)
    cashback = meta.get("cashback", 0)

    # Optional extra fields (for bottom left / payment plan)
    event_date = _safe_str(meta.get("event_date", meta.get("wedding_date", "")))
    venue = _safe_str(meta.get("venue", meta.get("event_venue", "")))

    bank_name = _safe_str(meta.get("bank_name", meta.get("bank_nm", ""))) or "-"
    bank_holder = _safe_str(meta.get("bank_holder", meta.get("bank_an", ""))) or "-"
    bank_acc = _safe_str(meta.get("bank_acc", meta.get("bank_ac", ""))) or "-"

    # Payment plan area
    payments = meta.get("payments", [])  # list of dict: {"label": "...", "amount": 0}
    remaining = meta.get("remaining_balance", None)  # int
    next_payment = _safe_str(meta.get("next_payment_text", ""))

    # -------------------------
    # 1) Top Banner (black)
    # -------------------------
    c.setFillColor(BLACK)
    c.rect(0, H - top_bar_h, W, top_bar_h, fill=1, stroke=0)

    # left logo block separator lines (white)
    c.setStrokeColor(WHITE)
    c.setLineWidth(1)
    c.line(margin + logo_block_w, H - top_bar_h, margin + logo_block_w, H)  # vertical sep

    # logo inside left block
    _try_draw_logo(
        c,
        x=margin + 6 * mm,
        y=H - top_bar_h + 4 * mm,
        w=logo_block_w - 12 * mm,
        h=top_bar_h - 8 * mm,
        logo_path=LOGO_PATH,
    )

    # diagonal ribbon tail (black triangle) below left block
    # mimic the sample: a diagonal cut that drops down into white area
    tail_left = margin
    tail_right = margin + logo_block_w
    tail_top = H - top_bar_h
    tail_bottom = tail_top - ribbon_drop
    _draw_polygon(
        c,
        points=[
            (tail_left, tail_top),
            (tail_right, tail_top),
            (tail_left, tail_bottom),
        ],
        fill_color=BLACK,
        stroke=0,
    )
    # white outline on the diagonal (subtle)
    c.setStrokeColor(WHITE)
    c.setLineWidth(1)
    c.line(tail_right, tail_top, tail_left, tail_bottom)

    # INVOICE title on the right
    c.setFillColor(WHITE)
    c.setFont("Times-Roman", 18)
    title_x = W - margin
    title_y = H - 16 * mm
    c.drawRightString(title_x, title_y, "INVOICE")
    # underline
    c.setLineWidth(1)
    c.line(W - margin - 52 * mm, title_y - 2 * mm, W - margin, title_y - 2 * mm)

    # -------------------------
    # 2) Invoice meta block (right under banner)
    # -------------------------
    meta_top_y = H - top_bar_h - 10 * mm

    # Left of this block: "INVOICE TO:"
    c.setFillColor(BLACK)
    c.setFont("Helvetica-Bold", 7)
    c.drawRightString(W - margin - 52 * mm, meta_top_y, "INVOICE TO :")
    c.setFont("Helvetica", 8)
    c.drawRightString(W - margin - 52 * mm, meta_top_y - 8 * mm, client.upper())

    # Right of this block: invoice# + date
    c.setFont("Helvetica-Bold", 7)
    c.drawRightString(W - margin, meta_top_y, f"INVOICE#:  {_safe_str(inv_no)}")
    c.drawRightString(W - margin, meta_top_y - 8 * mm, f"DATE :  {inv_date}")

    # -------------------------
    # 3) Table
    # -------------------------
    table_x = margin
    table_top_y = meta_top_y - 18 * mm  # start below meta block

    # Build paragraphs for item description (title + bullets)
    styles = getSampleStyleSheet()
    p_title = ParagraphStyle(
        "p_title",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.8,
        leading=11,
        textColor=BLACK,
        spaceAfter=2,
    )
    p_line = ParagraphStyle(
        "p_line",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.4,
        leading=9.6,
        textColor=BLACK,
    )

    def item_desc_paragraph(desc: str, details: str) -> Paragraph:
        desc = _safe_str(desc).strip() or "-"
        lines = []
        det_lines = [x.strip() for x in _safe_str(details).split("\n") if x.strip()]

        html = f"<b>{desc}</b>"
        if det_lines:
            html += "<br/>" + "<br/>".join([f"• {ln}" for ln in det_lines])
        return Paragraph(html, ParagraphStyle("mix", parent=p_line))

    # header
    data = [[
        Paragraph("<b>NO</b>", p_line),
        Paragraph("<b>ITEM DESCRIPTION</b>", p_line),
        Paragraph("<b>PRICE</b>", p_line),
        Paragraph("<b>QTY</b>", p_line),
        Paragraph("<b>TOTAL</b>", p_line),
    ]]

    # rows
    for i, it in enumerate(items or [], start=1):
        desc = it.get("Description", it.get("description", ""))
        qty = it.get("Qty", it.get("qty", 1))
        price = it.get("Price", it.get("price", 0))
        total = it.get("Total", it.get("total", 0))
        details = it.get("Details", it.get("details", ""))

        data.append([
            Paragraph(f"{i}", p_line),
            item_desc_paragraph(desc, details),
            Paragraph(f"Rp&nbsp;&nbsp;{_fmt_idr(price)}", p_line),
            Paragraph(f"{int(qty) if str(qty).isdigit() else qty}", p_line),
            Paragraph(f"Rp&nbsp;&nbsp;{_fmt_idr(total)}", p_line),
        ])

    # column widths (close to sample)
    col_w = [
        10 * mm,   # NO
        102 * mm,  # ITEM
        25 * mm,   # PRICE
        12 * mm,   # QTY
        25 * mm,   # TOTAL
    ]

    t = Table(data, colWidths=col_w)

    t.setStyle(TableStyle([
        # header row
        ("BACKGROUND", (0, 0), (-1, 0), BLACK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7.5),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("ALIGN", (2, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),

        # body
        ("VALIGN", (0, 1), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 1), (-1, -1), 7.4),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),

        ("ALIGN", (0, 1), (0, -1), "CENTER"),     # NO
        ("ALIGN", (2, 1), (2, -1), "RIGHT"),      # PRICE
        ("ALIGN", (3, 1), (3, -1), "CENTER"),     # QTY
        ("ALIGN", (4, 1), (4, -1), "RIGHT"),      # TOTAL

        # grid lines (thin, dark)
        ("GRID", (0, 0), (-1, -1), 0.6, LINE),
    ]))

    tw, th = t.wrapOn(c, W - 2 * margin, H)
    table_y = table_top_y - th
    t.drawOn(c, table_x, table_y)

    # -------------------------
    # 4) Bottom-left info (Wedding Date / Venue + Payment Info)
    # -------------------------
    bottom_left_y = table_y - 10 * mm
    c.setFillColor(BLACK)
    c.setFont("Helvetica", 8)

    if event_date.strip():
        c.drawString(margin, bottom_left_y, "Wedding Date")
        c.drawString(margin + 30 * mm, bottom_left_y, f":  {event_date}")
        bottom_left_y -= 5 * mm

    if venue.strip():
        c.drawString(margin, bottom_left_y, "Venue")
        c.drawString(margin + 30 * mm, bottom_left_y, f":  {venue}")
        bottom_left_y -= 7 * mm
    else:
        bottom_left_y -= 2 * mm

    # Payment Info block
    c.setFont("Helvetica-Bold", 8)
    c.drawString(margin, bottom_left_y, "Payment Info")
    bottom_left_y -= 6 * mm

    c.setFont("Helvetica", 8)
    c.drawString(margin, bottom_left_y, "Bank")
    c.drawString(margin + 30 * mm, bottom_left_y, f":  {bank_name}")
    bottom_left_y -= 5 * mm

    c.drawString(margin, bottom_left_y, "A/C Name")
    c.drawString(margin + 30 * mm, bottom_left_y, f":  {bank_holder}")
    bottom_left_y -= 5 * mm

    c.drawString(margin, bottom_left_y, "Account#")
    c.drawString(margin + 30 * mm, bottom_left_y, f":  {bank_acc}")

    # Thank you note (bottom)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(margin, 28 * mm, "Thankyou for trusting us")

    # -------------------------
    # 5) Totals box (bottom-right)
    # -------------------------
    box_w = 86 * mm
    box_x = W - margin - box_w
    box_y = table_y - 2 * mm  # anchor near table bottom

    row_h = 7.5 * mm

    # TOTAL row (black)
    c.setFillColor(BLACK)
    c.rect(box_x, box_y - row_h, box_w, row_h, fill=1, stroke=1)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(box_x + 6 * mm, box_y - row_h + 2.4 * mm, "TOTAL:")
    c.drawRightString(box_x + box_w - 6 * mm, box_y - row_h + 2.4 * mm, f"Rp  {_fmt_idr(subtotal)}")

    # Cashback row (white)
    y2 = box_y - (2 * row_h)
    c.setFillColor(WHITE)
    c.rect(box_x, y2, box_w, row_h, fill=1, stroke=1)
    c.setFillColor(BLACK)
    c.setFont("Helvetica", 8.7)
    c.drawString(box_x + 6 * mm, y2 + 2.4 * mm, "Cashback:")
    c.drawRightString(box_x + box_w - 6 * mm, y2 + 2.4 * mm, f"-Rp  {_fmt_idr(cashback)}")

    # GRAND TOTAL row (black)
    y3 = box_y - (3 * row_h)
    c.setFillColor(BLACK)
    c.rect(box_x, y3, box_w, row_h, fill=1, stroke=1)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(box_x + 6 * mm, y3 + 2.4 * mm, "GRAND TOTAL:")
    c.drawRightString(box_x + box_w - 6 * mm, y3 + 2.4 * mm, f"Rp  {_fmt_idr(grand_total)}")

    # Payment schedule list under totals
    y_list = y3 - 6 * mm
    c.setFillColor(BLACK)
    c.setFont("Helvetica", 7.8)

    # if payments provided, print like sample (Payment 1/2/3/Full)
    if isinstance(payments, list) and payments:
        for p in payments:
            label = _safe_str(p.get("label", "")).strip()
            amt = p.get("amount", "")
            if not label:
                continue
            c.drawString(box_x + 6 * mm, y_list, f"{label}:")
            c.drawRightString(box_x + box_w - 6 * mm, y_list, f"Rp  {_fmt_idr(amt)}" if str(amt).strip() else "-")
            y_list -= 4.6 * mm
        y_list -= 1.5 * mm

    # Remaining Balance
    if remaining is not None:
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(box_x + 6 * mm, y_list, "Remaining Balance:")
        c.drawRightString(box_x + box_w - 6 * mm, y_list, f"Rp  {_fmt_idr(remaining)}")
        y_list -= 7 * mm

    # Next payment bar (black)
    if next_payment.strip():
        bar_h = 7 * mm
        c.setFillColor(BLACK)
        c.rect(box_x, y_list - bar_h + 2 * mm, box_w, bar_h, fill=1, stroke=1)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 7.6)
        c.drawCentredString(box_x + box_w / 2, y_list - bar_h + 4.2 * mm, next_payment)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf
