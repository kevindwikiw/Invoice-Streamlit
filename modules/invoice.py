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
    """Draws a polygon shape (used for the header ribbon tail)."""
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
    """Draws logo if found, otherwise text."""
    if logo_path and os.path.exists(logo_path):
        try:
            img = ImageReader(logo_path)
            iw, ih = img.getSize()
            aspect = ih / float(iw)
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

    # Fallback Text
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(x + w / 2, y + h / 2 - 5, "ORBIT")

# =========================================================
# MAIN GENERATOR
# =========================================================
def generate_pdf_bytes(meta: dict, items: list, grand_total: int) -> BytesIO:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    # --- Constants & Colors ---
    BLACK = colors.HexColor("#0b0b0c")
    WHITE = colors.white
    LINE = colors.HexColor("#1b1b1c")
    
    margin = 18 * mm
    top_bar_h = 28 * mm
    logo_block_w = 58 * mm
    ribbon_drop = 18 * mm

    # --- Extract Meta Data ---
    # Basic Info
    inv_no = _safe_str(meta.get("inv_no", "0001"))
    title = _safe_str(meta.get("title", "")) # Event Title
    date_str = meta.get("date") or datetime.today().strftime("%d %B %Y")
    client = _safe_str(meta.get("client_name", "-"))

    # Wedding Info
    wedding_date = _safe_str(meta.get("wedding_date", ""))
    venue = _safe_str(meta.get("venue", ""))

    # Bank Info
    bank_nm = _safe_str(meta.get("bank_name", ""))
    bank_ac = _safe_str(meta.get("bank_acc", ""))
    bank_an = _safe_str(meta.get("bank_holder", ""))

    # Terms
    terms_text = _safe_str(meta.get("terms", ""))

    # Money
    subtotal = float(meta.get("subtotal", 0))
    cashback = float(meta.get("cashback", 0))
    # grand_total passed as argument

    # Payment Schedule (From View State)
    # We create a list of tuples: (Label, Amount)
    payment_plan = []
    if meta.get("pay_dp1", 0) > 0:
        payment_plan.append(("Down Payment 1", meta["pay_dp1"]))
    if meta.get("pay_term2", 0) > 0:
        payment_plan.append(("Payment 2 (H+7 Exhibition)", meta["pay_term2"]))
    if meta.get("pay_term3", 0) > 0:
        payment_plan.append(("Payment 3 (H-7 Prewedding)", meta["pay_term3"]))
    if meta.get("pay_full", 0) > 0:
        payment_plan.append(("Full Payment (H-7 Wedding)", meta["pay_full"]))

    # Calculate Remaining
    total_paid_plan = sum(p[1] for p in payment_plan)
    remaining = max(0, grand_total - total_paid_plan)

    # -------------------------
    # 1. HEADER BANNER
    # -------------------------
    c.setFillColor(BLACK)
    c.rect(0, H - top_bar_h, W, top_bar_h, fill=1, stroke=0)

    # Separator Line
    c.setStrokeColor(WHITE)
    c.setLineWidth(1)
    c.line(margin + logo_block_w, H - top_bar_h, margin + logo_block_w, H)

    # Logo
    _try_draw_logo(c, margin + 6*mm, H - top_bar_h + 4*mm, logo_block_w - 12*mm, top_bar_h - 8*mm, "assets/logo.png")

    # Diagonal Tail
    tail_pts = [
        (margin, H - top_bar_h),
        (margin + logo_block_w, H - top_bar_h),
        (margin, H - top_bar_h - ribbon_drop)
    ]
    _draw_polygon(c, tail_pts, fill_color=BLACK, stroke=0)
    c.setStrokeColor(WHITE)
    c.line(tail_pts[1][0], tail_pts[1][1], tail_pts[2][0], tail_pts[2][1])

    # "INVOICE" Text
    c.setFillColor(WHITE)
    c.setFont("Times-Roman", 18)
    c.drawRightString(W - margin, H - 16*mm, "INVOICE")
    c.setLineWidth(1)
    c.line(W - margin - 52*mm, H - 18*mm, W - margin, H - 18*mm)

    # -------------------------
    # 2. INVOICE META
    # -------------------------
    y_meta = H - top_bar_h - 10 * mm
    
    # Left Side: To Client
    c.setFillColor(BLACK)
    c.setFont("Helvetica-Bold", 7)
    c.drawRightString(W - margin - 52*mm, y_meta, "INVOICE TO :")
    
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(W - margin - 52*mm, y_meta - 5*mm, client.upper())
    
    if title:
        c.setFont("Helvetica-Oblique", 7)
        c.drawRightString(W - margin - 52*mm, y_meta - 9*mm, title)

    # Right Side: No & Date
    c.setFont("Helvetica-Bold", 7)
    c.drawRightString(W - margin, y_meta, f"INVOICE#:  {inv_no}")
    c.drawRightString(W - margin, y_meta - 5*mm, f"DATE :  {date_str}")

    # -------------------------
    # 3. TABLE ITEMS
    # -------------------------
    table_y_start = y_meta - 18 * mm
    
    # Styles
    styles = getSampleStyleSheet()
    style_item = ParagraphStyle("item", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=10)
    style_desc = ParagraphStyle("desc", parent=styles["Normal"], fontName="Helvetica", fontSize=7.5, leading=9, leftIndent=0)

    # Build Data
    data = [[
        "NO", "ITEM DESCRIPTION", "PRICE", "QTY", "TOTAL"
    ]]

    for i, it in enumerate(items, 1):
        desc_txt = _safe_str(it.get("Description", ""))
        det_txt = _safe_str(it.get("Details", ""))
        
        # Combine Desc + Details
        cell_xml = f"<b>{desc_txt}</b>"
        if det_txt:
            lines = [l.strip() for l in det_txt.split('\n') if l.strip()]
            if lines:
                cell_xml += "<br/><br/>" + "<br/>".join([f"• {l}" for l in lines])
        
        p = Paragraph(cell_xml, style_desc)
        
        row = [
            str(i),
            p,
            f"Rp {_fmt_idr(it.get('Price', 0))}",
            str(int(it.get('Qty', 1))),
            f"Rp {_fmt_idr(it.get('Total', 0))}"
        ]
        data.append(row)

    # Table Layout
    col_widths = [10*mm, 102*mm, 25*mm, 12*mm, 25*mm]
    t = Table(data, colWidths=col_widths)
    
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), BLACK),
        ('TEXTCOLOR', (0,0), (-1,0), WHITE),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 7.5),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,0), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        
        # Rows
        ('VALIGN', (0,1), (-1,-1), 'TOP'),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 7.5),
        ('TOPPADDING', (0,1), (-1,-1), 6),
        ('BOTTOMPADDING', (0,1), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, LINE),
        
        # Column Alignments
        ('ALIGN', (0,1), (0,-1), 'CENTER'), # NO
        ('ALIGN', (1,1), (1,-1), 'LEFT'),   # DESC
        ('ALIGN', (2,1), (2,-1), 'RIGHT'),  # PRICE
        ('ALIGN', (3,1), (3,-1), 'CENTER'), # QTY
        ('ALIGN', (4,1), (4,-1), 'RIGHT'),  # TOTAL
    ]))

    w_table, h_table = t.wrapOn(c, W, H)
    t.drawOn(c, margin, table_y_start - h_table)
    
    cursor_y = table_y_start - h_table - 8*mm

    # -------------------------
    # 4. BOTTOM SECTIONS
    # -------------------------
    
    # --- LEFT SIDE: INFO & TERMS ---
    left_x = margin
    
    c.setFillColor(BLACK)
    
    # 4a. Wedding Info
    if wedding_date or venue:
        c.setFont("Helvetica-Bold", 8)
        c.drawString(left_x, cursor_y, "Event Details:")
        cursor_y -= 4*mm
        
        c.setFont("Helvetica", 8)
        if wedding_date:
            c.drawString(left_x, cursor_y, f"Date: {wedding_date}")
            cursor_y -= 4*mm
        if venue:
            c.drawString(left_x, cursor_y, f"Venue: {venue}")
            cursor_y -= 6*mm
    
    # 4b. Payment Info
    c.setFont("Helvetica-Bold", 8)
    c.drawString(left_x, cursor_y, "Payment Info:")
    cursor_y -= 4*mm
    
    c.setFont("Helvetica", 8)
    c.drawString(left_x, cursor_y, f"Bank: {bank_nm}")
    cursor_y -= 4*mm
    c.drawString(left_x, cursor_y, f"Acc: {bank_ac}")
    cursor_y -= 4*mm
    c.drawString(left_x, cursor_y, f"A/N: {bank_an}")
    cursor_y -= 8*mm

    # 4c. Terms & Conditions
    if terms_text:
        c.setFont("Helvetica-Bold", 8)
        c.drawString(left_x, cursor_y, "Terms & Conditions:")
        cursor_y -= 4*mm
        
        c.setFont("Helvetica", 7)
        # Split terms by newline
        term_lines = terms_text.split('\n')
        for line in term_lines:
            if line.strip():
                c.drawString(left_x, cursor_y, line.strip())
                cursor_y -= 3*mm

    # --- RIGHT SIDE: TOTALS & SCHEDULE ---
    # Box Position
    box_w = 86 * mm
    box_x = W - margin - box_w
    # Start box higher up, aligned with top of left info
    box_y = table_y_start - h_table - 4*mm 
    
    row_h = 7 * mm
    
    # Helper to draw summary row
    def draw_summary_row(label, val_str, bg_color, text_color, is_bold=False):
        nonlocal box_y
        c.setFillColor(bg_color)
        c.rect(box_x, box_y - row_h, box_w, row_h, fill=1, stroke=1)
        
        c.setFillColor(text_color)
        font = "Helvetica-Bold" if is_bold else "Helvetica"
        c.setFont(font, 9 if is_bold else 8)
        
        c.drawString(box_x + 4*mm, box_y - row_h + 2.5*mm, label)
        c.drawRightString(box_x + box_w - 4*mm, box_y - row_h + 2.5*mm, val_str)
        box_y -= row_h

    # 1. Subtotal
    draw_summary_row("SUBTOTAL", f"Rp {_fmt_idr(subtotal)}", WHITE, BLACK)
    
    # 2. Cashback (if any)
    if cashback > 0:
        draw_summary_row("CASHBACK", f"- Rp {_fmt_idr(cashback)}", WHITE, BLACK)
        
    # 3. GRAND TOTAL
    draw_summary_row("GRAND TOTAL", f"Rp {_fmt_idr(grand_total)}", BLACK, WHITE, is_bold=True)
    
    # Spacer
    box_y -= 4*mm
    
    # 4. PAYMENT SCHEDULE LIST
    if payment_plan:
        c.setFillColor(BLACK)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(box_x, box_y, "Payment Schedule:")
        box_y -= 4*mm
        
        c.setFont("Helvetica", 8)
        for label, amt in payment_plan:
            c.drawString(box_x + 2*mm, box_y, label)
            c.drawRightString(box_x + box_w, box_y, f"Rp {_fmt_idr(amt)}")
            box_y -= 4*mm
            
        # Divider line
        c.setStrokeColor(LINE)
        c.line(box_x, box_y + 1*mm, box_x + box_w, box_y + 1*mm)
        box_y -= 2*mm
        
        # Remaining
        c.setFont("Helvetica-Bold", 9)
        c.drawString(box_x, box_y, "Remaining Balance:")
        c.drawRightString(box_x + box_w, box_y, f"Rp {_fmt_idr(remaining)}")

    # Footer Note
    c.setFillColor(colors.HexColor("#555555"))
    c.setFont("Helvetica-Oblique", 7)
    c.drawCentredString(W/2, 10*mm, "Thank you for trusting us with your special moments.")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf
