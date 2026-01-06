# modules/invoice.py
import os
from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

# =========================================================
# Helpers
# =========================================================
def _fmt_currency(val) -> str:
    """
    Format angka ke Rupiah. 
    Jika 0 atau None -> Return 'FREE' (tanpa Rp).
    """
    try:
        n = float(val)
    except:
        n = 0
    
    if n == 0:
        return "FREE"
    
    # Rounding & Formatting
    return f"Rp {int(round(n)):,}".replace(",", ".")

def _safe_str(x) -> str:
    return "" if x is None else str(x)

def _draw_polygon(c: canvas.Canvas, points, fill_color=colors.black, stroke_color=None, stroke=0):
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
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(x + w / 2, y + h / 2 - 5, "ORBIT")

def _draw_wrapped_text(c, text, x, y, max_w, font="Helvetica", font_size=7, leading=3*mm):
    c.setFont(font, font_size)
    for raw in (text or "").split("\n"):
        line = raw.strip()
        if not line:
            y -= leading
            continue
        for wline in simpleSplit(line, font, font_size, max_w):
            c.drawString(x, y, wline)
            y -= leading
    return y

def _details_to_bullets(det_txt: str, indent=False) -> str:
    det_txt = _safe_str(det_txt)
    lines = [l.strip() for l in det_txt.split("\n") if l.strip()]
    if not lines: return ""
    bullet = "&bull;" 
    if indent: bullet = "&nbsp;&nbsp;-" 
    return "<br/>".join([f"{bullet} {l}" for l in lines])

def _draw_underlined_header(c, text, x, y, font="Helvetica-Bold", size=9):
    """Menggambar text bold dengan garis bawah custom."""
    c.setFillColor(colors.black)
    c.setFont(font, size)
    c.drawString(x, y, text)
    
    # Hitung lebar text untuk garis bawah
    text_w = c.stringWidth(text, font, size)
    c.setLineWidth(1)
    c.setStrokeColor(colors.black)
    # Gambar garis sedikit di bawah text
    c.line(x, y - 3, x + text_w, y - 3)
    
    return y - 5 * mm # Return cursor baru

# =========================================================
# MAIN GENERATOR
# =========================================================
def generate_pdf_bytes(meta: dict, items: list, grand_total: int) -> BytesIO:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    # --- Colors & Metrics ---
    BLACK = colors.HexColor("#1a1a1a")
    DARK_GRAY = colors.HexColor("#4a4a4a")
    WHITE = colors.white
    LINE_COLOR = colors.HexColor("#000000") 

    margin = 15 * mm
    top_bar_h = 30 * mm
    logo_block_w = 60 * mm
    ribbon_drop = 15 * mm

    # --- Extract Data ---
    inv_no = _safe_str(meta.get("inv_no", "0000"))
    title = _safe_str(meta.get("title", ""))
    date_str = meta.get("date") or datetime.today().strftime("%d %B %Y")
    client = _safe_str(meta.get("client_name", "-"))
    
    wedding_date = _safe_str(meta.get("wedding_date", ""))
    venue = _safe_str(meta.get("venue", ""))
    
    bank_nm = _safe_str(meta.get("bank_name", ""))
    bank_ac = _safe_str(meta.get("bank_acc", ""))
    bank_an = _safe_str(meta.get("bank_holder", ""))
    
    terms_text = _safe_str(meta.get("terms", ""))

    subtotal = float(meta.get("subtotal", 0))
    cashback = float(meta.get("cashback", 0))

    payment_plan = []
    if meta.get("pay_dp1", 0) > 0: payment_plan.append(("Down Payment", meta["pay_dp1"]))
    if meta.get("pay_term2", 0) > 0: payment_plan.append(("Payment 2", meta["pay_term2"]))
    if meta.get("pay_term3", 0) > 0: payment_plan.append(("Payment 3", meta["pay_term3"]))
    if meta.get("pay_full", 0) > 0: payment_plan.append(("Pelunasan", meta["pay_full"]))

    total_paid_scheduled = sum(p[1] for p in payment_plan)
    remaining = max(0, grand_total - total_paid_scheduled)

    # =========================================================
    # 1. HEADER
    # =========================================================
    c.setFillColor(BLACK)
    c.rect(0, H - top_bar_h, W, top_bar_h, fill=1, stroke=0)
    c.setStrokeColor(WHITE)
    c.setLineWidth(0.5)
    c.line(margin + logo_block_w, H - top_bar_h, margin + logo_block_w, H)

    _try_draw_logo(c, margin + 2*mm, H - top_bar_h + 2*mm, logo_block_w - 4*mm, top_bar_h - 4*mm, "assets/logo.png")

    tail_pts = [(margin, H - top_bar_h), (margin + logo_block_w, H - top_bar_h), (margin, H - top_bar_h - ribbon_drop)]
    _draw_polygon(c, tail_pts, fill_color=BLACK, stroke=0)
    c.setStrokeColor(WHITE)
    c.line(tail_pts[1][0], tail_pts[1][1], tail_pts[2][0], tail_pts[2][1])

    invoice_title_text = "INVOICE"
    c.setFillColor(WHITE)
    c.setFont("Times-Bold", 22)
    c.drawRightString(W - margin, H - 20 * mm, invoice_title_text)
    
    title_width = c.stringWidth(invoice_title_text, "Times-Bold", 22)
    c.setLineWidth(1)
    c.line(W - margin - title_width, H - 22 * mm, W - margin, H - 22 * mm)

    # =========================================================
    # 2. METADATA
    # =========================================================
    y_meta = H - top_bar_h - 12 * mm

    c.setFillColor(DARK_GRAY)
    c.setFont("Helvetica-Bold", 8)
    c.drawRightString(W - margin - 60 * mm, y_meta, "INVOICE TO")
    c.setFillColor(BLACK)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(W - margin - 60 * mm, y_meta - 5 * mm, client.upper())
    
    if title:
        c.setFillColor(DARK_GRAY)
        c.setFont("Helvetica-Oblique", 8)
        c.drawRightString(W - margin - 60 * mm, y_meta - 9 * mm, title)

    c.setFillColor(DARK_GRAY)
    c.setFont("Helvetica", 8)
    c.drawRightString(W - margin, y_meta, f"Invoice #: {inv_no}")
    c.drawRightString(W - margin, y_meta - 4 * mm, f"Date: {date_str}")


    # =========================================================
    # 3. ITEM TABLE (MAIN)
    # =========================================================
    table_y_start = y_meta - 16 * mm

    styles = getSampleStyleSheet()
    style_desc = ParagraphStyle("desc", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=10, textColor=BLACK)
    style_header = ParagraphStyle("header", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, textColor=WHITE, alignment=TA_CENTER)

    # Headers
    headers = [
        Paragraph("NO", style_header),
        Paragraph("ITEM DESCRIPTION", ParagraphStyle("h_desc", parent=style_header, alignment=TA_LEFT)),
        Paragraph("PRICE", ParagraphStyle("h_right", parent=style_header, alignment=TA_RIGHT)),
        Paragraph("QTY", style_header),
        Paragraph("TOTAL", ParagraphStyle("h_right", parent=style_header, alignment=TA_RIGHT)),
    ]
    
    data = [headers]
    row_idx = 1
    item_no = 1

    for it in (items or []):
        is_bundle = bool(it.get("_bundle"))
        
        if not is_bundle:
            desc_txt = _safe_str(it.get("Description", ""))
            det_txt = _safe_str(it.get("Details", ""))
            cell_xml = f"<b>{desc_txt}</b>"
            bullets = _details_to_bullets(det_txt)
            if bullets: cell_xml += f"<br/><font size=7 color='#555555'>{bullets}</font>"
            
            data.append([
                str(item_no),
                Paragraph(cell_xml, style_desc),
                _fmt_currency(it.get('Price', 0)), # Use new formatter
                str(int(it.get("Qty", 1))),
                _fmt_currency(it.get('Total', 0))  # Use new formatter
            ])
        else:
            bundle_title = _safe_str(it.get("Description", "BUNDLING")).strip()
            src_items = it.get("_bundle_src", [])
            full_desc_html = f"<b>{bundle_title}</b><br/><br/>"
            for sub in src_items:
                s_name = _safe_str(sub.get("Description", ""))
                s_det = _safe_str(sub.get("Details", ""))
                full_desc_html += f"<b>&bull; {s_name}</b><br/>"
                bullets = _details_to_bullets(s_det, indent=True)
                if bullets: full_desc_html += f"<font size=7 color='#666666'>{bullets}</font><br/>"
                full_desc_html += "<br/>"

            data.append([
                str(item_no),
                Paragraph(full_desc_html, style_desc),
                _fmt_currency(it.get('Price', 0)),
                "1",
                _fmt_currency(it.get('Total', 0))
            ])
        
        item_no += 1
        row_idx += 1

    col_widths = [10 * mm, 95 * mm, 30 * mm, 12 * mm, 30 * mm]
    
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLACK),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE_COLOR), 
        ("VALIGN", (0, 1), (-1, -1), "TOP"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (0, 1), (0, -1), "CENTER"), 
        ("ALIGN", (1, 1), (1, -1), "LEFT"),   
        ("ALIGN", (2, 1), (2, -1), "RIGHT"),  
        ("ALIGN", (3, 1), (3, -1), "CENTER"), 
        ("ALIGN", (4, 1), (4, -1), "RIGHT"),  
        ("topPadding", (0, 1), (-1, -1), 8),
        ("bottomPadding", (0, 1), (-1, -1), 8),
    ]))

    w_table, h_table = t.wrapOn(c, W, H)
    t.drawOn(c, margin, table_y_start - h_table)
    
    cursor_y = table_y_start - h_table

    # =========================================================
    # 4. SUMMARY SECTION (ESTETIK BLACK BAR)
    # =========================================================
    summary_data = []
    
    # 1. TOTAL (Black Bar)
    # Gunakan 'TOTAL:' sebagai label untuk subtotal agar match dengan referensi
    summary_data.append(['', '', 'TOTAL:', '', _fmt_currency(subtotal)])
    
    # 2. Cashback (White Bar)
    if cashback > 0:
        summary_data.append(['', '', 'Cashback:', '', f"- {_fmt_currency(cashback)}"])
    
    # 3. GRAND TOTAL (Black Bar, Big Font)
    summary_data.append(['', '', 'GRAND TOTAL:', '', _fmt_currency(grand_total)])
    
    # 4. Payment History (Plain)
    if payment_plan:
        summary_data.append(['', '', 'Payment History:', '', '']) # Spacer header row
        for label, amt in payment_plan:
             summary_data.append(['', '', label, '', _fmt_currency(amt)])
             
    # 5. Remaining (Plain but Bold)
    summary_data.append(['', '', 'SISA TAGIHAN:', '', _fmt_currency(remaining)])

    t_sum = Table(summary_data, colWidths=col_widths)
    
    sum_styles = [
        # Alignments (Tetap dijaga agar lurus dengan tabel atas)
        ("ALIGN", (2, 0), (2, -1), "RIGHT"), # Label
        ("ALIGN", (4, 0), (4, -1), "RIGHT"), # Value
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        
        # Default Padding
        ("topPadding", (0, 0), (-1, -1), 5),
        ("bottomPadding", (0, 0), (-1, -1), 5),
    ]

    # SPANNING (Merge Col 2 & 3 for Label)
    for r in range(len(summary_data)):
        sum_styles.append(("SPAN", (2, r), (3, r)))

    # --- APPLYING THE "AESTHETIC" STYLES ---
    
    # 1. TOTAL ROW (Subtotal) -> BLACK BG, WHITE TEXT, BOLD
    sum_styles.append(("BACKGROUND", (2, 0), (4, 0), BLACK))
    sum_styles.append(("TEXTCOLOR", (2, 0), (4, 0), WHITE))
    sum_styles.append(("FONTNAME", (2, 0), (4, 0), "Helvetica-Bold"))
    
    # 2. CASHBACK ROW -> Bold Label
    if cashback > 0:
        sum_styles.append(("FONTNAME", (2, 1), (4, 1), "Helvetica-Bold"))
    
    # 3. GRAND TOTAL ROW -> BLACK BG, WHITE TEXT, BIGGER FONT
    gt_idx = 2 if cashback > 0 else 1
    sum_styles.append(("BACKGROUND", (2, gt_idx), (4, gt_idx), BLACK))
    sum_styles.append(("TEXTCOLOR", (2, gt_idx), (4, gt_idx), WHITE))
    sum_styles.append(("FONTNAME", (2, gt_idx), (4, gt_idx), "Helvetica-Bold"))
    sum_styles.append(("FONTSIZE", (2, gt_idx), (4, gt_idx), 11)) # Bigger Font
    sum_styles.append(("topPadding", (2, gt_idx), (4, gt_idx), 8))
    sum_styles.append(("bottomPadding", (2, gt_idx), (4, gt_idx), 8))

    # 4. Payment History Styling
    if payment_plan:
        ph_idx = gt_idx + 1
        sum_styles.append(("FONTNAME", (2, ph_idx), (4, ph_idx), "Helvetica-BoldOblique"))
        sum_styles.append(("TEXTCOLOR", (2, ph_idx), (4, ph_idx), DARK_GRAY))
        # Isi history (baris setelah header history sampai sebelum remaining)
        start_hist = ph_idx + 1
        end_hist = len(summary_data) - 2 # -1 karena last row is remaining
        if start_hist <= end_hist:
            sum_styles.append(("FONTNAME", (2, start_hist), (4, end_hist), "Helvetica"))
            sum_styles.append(("TEXTCOLOR", (2, start_hist), (4, end_hist), BLACK))

    # 5. Remaining Balance (Last Row) -> RED & BOLD
    last_row = len(summary_data) - 1
    sum_styles.append(("FONTNAME", (2, last_row), (4, last_row), "Helvetica-Bold"))
    sum_styles.append(("TEXTCOLOR", (2, last_row), (4, last_row), colors.HexColor("#b91c1c"))) 
    sum_styles.append(("topPadding", (2, last_row), (4, last_row), 8))

    t_sum.setStyle(TableStyle(sum_styles))
    
    w_sum, h_sum = t_sum.wrapOn(c, W, H)
    t_sum.drawOn(c, margin, cursor_y - h_sum)


    # =========================================================
    # 5. INFO SECTION (LEFT SIDE - AESTHETIC HEADERS)
    # =========================================================
    info_y = cursor_y - 10 
    left_x = margin
    info_w = col_widths[0] + col_widths[1] - 5*mm 

    # --- EVENT DETAILS ---
    if wedding_date or venue:
        # Gambar Header dengan Underline
        info_y = _draw_underlined_header(c, "EVENT DETAILS:", left_x, info_y)
        
        c.setFont("Helvetica", 9)
        c.setFillColor(BLACK)
        
        # Render Date & Venue dengan Label Bold manual (simulasi)
        if wedding_date:
            c.setFont("Helvetica-Bold", 8)
            c.drawString(left_x, info_y, "Date:")
            c.setFont("Helvetica", 8)
            c.drawString(left_x + 10*mm, info_y, wedding_date)
            info_y -= 4 * mm
            
        if venue:
            c.setFont("Helvetica-Bold", 8)
            c.drawString(left_x, info_y, "Venue:")
            c.setFont("Helvetica", 8)
            c.drawString(left_x + 10*mm, info_y, venue)
            info_y -= 8 * mm # Extra space after section
            
    # --- PAYMENT INFO ---
    info_y = _draw_underlined_header(c, "PAYMENT INFO:", left_x, info_y)
    
    c.setFont("Helvetica", 8)
    c.setFillColor(BLACK)
    
    # Bank Label Bold
    c.setFont("Helvetica-Bold", 8)
    c.drawString(left_x, info_y, "Bank:")
    c.setFont("Helvetica", 8)
    c.drawString(left_x + 15*mm, info_y, bank_nm)
    info_y -= 4 * mm
    
    # Acc Label Bold
    c.setFont("Helvetica-Bold", 8)
    c.drawString(left_x, info_y, "Account:")
    c.setFont("Helvetica", 8)
    c.drawString(left_x + 15*mm, info_y, bank_ac)
    info_y -= 4 * mm
    
    # Name Label Bold
    c.setFont("Helvetica-Bold", 8)
    c.drawString(left_x, info_y, "A/N:")
    c.setFont("Helvetica", 8)
    c.drawString(left_x + 15*mm, info_y, bank_an)
    info_y -= 8 * mm

    # --- TERMS ---
    if terms_text:
        info_y = _draw_underlined_header(c, "TERMS & CONDITIONS:", left_x, info_y)
        c.setFillColor(DARK_GRAY)
        _draw_wrapped_text(c, terms_text, left_x, info_y, max_w=info_w, font="Helvetica", font_size=7, leading=3*mm)

    # =========================================================
    # 6. FOOTER
    # =========================================================
    c.setFillColor(colors.HexColor("#9ca3af")) 
    c.setFont("Helvetica-Oblique", 7)
    c.drawCentredString(W / 2, 8 * mm, "Thank you for trusting us with your special moments.")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf
