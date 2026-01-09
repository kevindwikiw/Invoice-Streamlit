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
    try:
        n = float(val)
    except:
        n = 0
    if n == 0:
        return "FREE"
    return f"Rp {int(round(n)):,}".replace(",", ".")

def _fmt_payment_row(val) -> str:
    try:
        n = float(val)
    except:
        n = 0
    if n == 0:
        return "-" 
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

def _calculate_dynamic_font(text, max_w):
    if not text:
        return 7, 3*mm
    lines_9 = []
    for raw in text.split('\n'):
        if raw.strip():
            lines_9.extend(simpleSplit(raw.strip(), "Helvetica", 9, max_w))
    if len(lines_9) <= 2:
        return 9, 4.5*mm 
    lines_8 = []
    for raw in text.split('\n'):
        if raw.strip():
            lines_8.extend(simpleSplit(raw.strip(), "Helvetica", 8, max_w))
    if len(lines_8) <= 5:
        return 8, 4*mm 
    return 7, 3*mm

def _details_to_bullets(det_txt: str, indent=False) -> str:
    det_txt = _safe_str(det_txt)
    lines = [l.strip() for l in det_txt.split("\n") if l.strip()]
    if not lines: return ""
    bullet = "&bull;" 
    if indent: bullet = "&nbsp;&nbsp;-" 
    return "<br/>".join([f"{bullet} {l}" for l in lines])

def _draw_underlined_header(c, text, x, y, font="Helvetica-Bold", size=9):
    c.setFillColor(colors.black)
    c.setFont(font, size)
    c.drawString(x, y, text)
    text_w = c.stringWidth(text, font, size)
    c.setLineWidth(1)
    c.setStrokeColor(colors.black)
    c.line(x, y - 3, x + text_w, y - 3)
    return y - 5 * mm 

# Imports for font registration
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def _draw_footer_contact(c, W):
    bar_h = 10 * mm
    c.setFillColor(colors.HexColor("#1a1a1a"))
    c.rect(0, 0, W, bar_h, fill=1, stroke=0)
    
    # 1. Font Setup
    emoji_font = "Helvetica"
    try:
        pdfmetrics.registerFont(TTFont('SegoeEmoji', 'C:\\Windows\\Fonts\\seguiemj.ttf'))
        emoji_font = 'SegoeEmoji'
    except:
        pass
        
    # 2. Define Data items as SINGLE STRINGS
    # User Request: "testing jadi 1 baris aja gausah dipisah... itu yg bikin error"
    # Merging icon and text into one string guarantees they are on the same baseline.
    items = [
        "📍 Jl. Panembakan Gg Sukamaju 15 No. 3, Kota Cimahi",
        "📧 theorbitphoto@gmail.com",
        "📸 @theorbitphoto",
        "📞 0813-2333-1506"
    ]
    
    # 3. Font Setup
    # Must use a font that supports BOTH Emoji and Text for the single string.
    # Segoe UI Emoji is perfect for this on Windows.
    use_font = emoji_font if emoji_font != "Helvetica" else "Helvetica"
    font_size = 7
    
    sep_str = "     |     "
    
    # 4. Measure Total Width
    total_w = 0
    item_widths = [] 
    
    sep_w = c.stringWidth(sep_str, use_font, font_size)
    
    for txt in items:
        # Measure entire string (Icon + Text) at once
        try:
            w_t = c.stringWidth(txt, use_font, font_size)
        except:
             # Fallback if measurer fails on weird chars
            w_t = c.stringWidth(txt, "Helvetica", font_size)
            
        item_widths.append(w_t)
        total_w += w_t
        
    # Add separators width
    if len(items) > 1:
        total_w += sep_w * (len(items) - 1)
    
    # 5. Draw Loop
    # Vertical Alignment: 
    # Center of 10mm bar. 
    # 4mm is a safe baseline for 7pt text.
    y_baseline = 4.0 * mm 
    
    cur_x = (W - total_w) / 2
    
    c.setFillColor(colors.white)
    c.setFont(use_font, font_size)
    
    for i, txt in enumerate(items):
        w_t = item_widths[i]
        
        # Draw the single string (Icon + Text naturally aligned)
        c.drawString(cur_x, y_baseline, txt)
        cur_x += w_t
        
        # Draw Separator
        if i < len(items) - 1:
            c.drawString(cur_x, y_baseline, sep_str)
            cur_x += sep_w

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
    RED = colors.HexColor("#b91c1c")
    LINE_COLOR = colors.HexColor("#000000") 

    margin = 15 * mm
    top_bar_h = 30 * mm
    logo_block_w = 60 * mm
    ribbon_drop = 15 * mm

    # --- Extract Data ---
    hari_id = {
        'Monday': 'Senin',
        'Tuesday': 'Selasa',
        'Wednesday': 'Rabu',
        'Thursday': 'Kamis',
        'Friday': 'Jumat',
        'Saturday': 'Sabtu',
        'Sunday': 'Minggu'
    }
    
    date_raw = meta.get("date")
    if date_raw:
        dt = datetime.strptime(date_raw, '%d %B %Y')
    else:
        dt = datetime.today()
    
    date_str = f"{hari_id[dt.strftime('%A')]}, {dt.strftime('%d %B %Y')}"
    
    inv_no = _safe_str(meta.get("inv_no", "0000"))
    title = _safe_str(meta.get("title", ""))
    client = _safe_str(meta.get("client_name", "-"))
    
    wedding_date = _safe_str(meta.get("wedding_date", ""))
    venue = _safe_str(meta.get("venue", ""))
    
    bank_nm = _safe_str(meta.get("bank_name", ""))
    bank_ac = _safe_str(meta.get("bank_acc", ""))
    bank_an = _safe_str(meta.get("bank_holder", ""))
    
    terms_text = _safe_str(meta.get("terms", ""))

    subtotal = float(meta.get("subtotal", 0))
    cashback = float(meta.get("cashback", 0))

    p_dp1 = float(meta.get("pay_dp1", 0))
    p_t2 = float(meta.get("pay_term2", 0))
    p_t3 = float(meta.get("pay_term3", 0))
    p_full = float(meta.get("pay_full", 0))

    payment_plan = [
        ("Down Payment", p_dp1),
        ("Payment 2", p_t2),
        ("Payment 3", p_t3),
        ("Pelunasan", p_full),
    ]

    total_paid_scheduled = sum(amt for _, amt in payment_plan)
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
    # 3. ITEM TABLE
    # =========================================================
    table_y_start = y_meta - 16 * mm

    styles = getSampleStyleSheet()
    style_desc = ParagraphStyle("desc", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=10, textColor=BLACK)
    style_header = ParagraphStyle("header", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, textColor=WHITE, alignment=TA_CENTER)

    headers = [
        Paragraph("NO", style_header),
        Paragraph("ITEM DESCRIPTION", ParagraphStyle("h_desc", parent=style_header, alignment=TA_CENTER)),
        Paragraph("PRICE", ParagraphStyle("h_right", parent=style_header, alignment=TA_CENTER)),
        Paragraph("QTY", style_header),
        Paragraph("TOTAL", ParagraphStyle("h_right", parent=style_header, alignment=TA_CENTER)),
    ]
    
    data = [headers]
    item_no = 1

    for it in (items or []):
        price_val = it.get('Price', 0)
        total_val = it.get('Total', 0)
        
        price_str = "FREE" if price_val == 0 else f"{_fmt_currency(price_val)}"
        total_str = "FREE" if total_val == 0 else f"{_fmt_currency(total_val)}"

        is_bundle = bool(it.get("_bundle"))
        
        if not is_bundle:
            desc_txt = _safe_str(it.get("Description", ""))
            det_txt = _safe_str(it.get("Details", ""))
            cell_xml = f"<b>{desc_txt}</b>"
            bullets = _details_to_bullets(det_txt)
            if bullets: cell_xml += f"<br/><font size=7 color='#555555'>{bullets}</font>"
            data.append([str(item_no), Paragraph(cell_xml, style_desc), price_str, str(int(it.get("Qty", 1))), total_str])
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
            data.append([str(item_no), Paragraph(full_desc_html, style_desc), price_str, "1", total_str])
        item_no += 1

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
    
    # Cursor moves to bottom of the table
    cursor_y_after_table = table_y_start - h_table 

    # =========================================================
    # 4. SUMMARY SECTION (SEPARATE BUT ATTACHED)
    # =========================================================
    summary_rows = []
    row_meta = [] 

    # 1. TOTAL (Filled Black)
    summary_rows.append(["", "", "TOTAL:", "", _fmt_currency(subtotal)])
    row_meta.append("total")

    # 2. Cashback
    if cashback > 0:
        summary_rows.append(["", "", "Cashback:", "", f"- {_fmt_currency(cashback)}"])
        row_meta.append("cashback")

    # 3. GRAND TOTAL (Filled Black)
    summary_rows.append(["", "", "GRAND TOTAL:", "", _fmt_currency(grand_total)])
    row_meta.append("grand")

    # 4. Payment History (Small)
    if payment_plan:
        summary_rows.append(["", "", "PAYMENT HISTORY", "", ""])
        row_meta.append("ph_header")
        for label, amt in payment_plan:
            val_str = f"- {_fmt_payment_row(amt)}" if amt > 0 else "-"
            summary_rows.append(["", "", label + ":", "", val_str])
            row_meta.append("ph_item")

    # 5. Remaining
    rem_str = "LUNAS" if remaining <= 0 else _fmt_currency(remaining)
    summary_rows.append(["", "", "SISA TAGIHAN (REMAINING):", "", rem_str])
    row_meta.append("remaining")

    # Gunakan colWidths SAMA dengan tabel item agar LURUS
    t_sum = Table(summary_rows, colWidths=col_widths)

    sum_styles = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("ALIGN", (4, 0), (4, -1), "RIGHT"),
    ]

    # Merge col 2 & 3 for Labels
    for r in range(len(summary_rows)):
        sum_styles.append(("SPAN", (2, r), (3, r)))

    # Style per row type
    for r, typ in enumerate(row_meta):
        if typ == "total":
            sum_styles += [
                ("BACKGROUND", (2, r), (4, r), BLACK),
                ("TEXTCOLOR", (2, r), (4, r), WHITE),
                ("FONTNAME", (2, r), (4, r), "Helvetica-Bold"),
                # --- UKURAN FONT TOTAL (BESAR) ---
                ("FONTSIZE", (2, r), (4, r), 10), 
                ("TOPPADDING", (0, r), (-1, r), 6), 
                ("BOTTOMPADDING", (0, r), (-1, r), 6),
            ]
        elif typ == "grand":
            sum_styles += [
                ("BACKGROUND", (2, r), (4, r), BLACK),
                ("TEXTCOLOR", (2, r), (4, r), WHITE),
                ("FONTNAME", (2, r), (4, r), "Helvetica-Bold"),
                # --- UKURAN FONT GRAND TOTAL (LEBIH BESAR) ---
                ("FONTSIZE", (2, r), (4, r), 12),
                ("TOPPADDING", (0, r), (-1, r), 8), 
                ("BOTTOMPADDING", (0, r), (-1, r), 8),
            ]
        elif typ == "cashback":
            sum_styles += [
                ("TEXTCOLOR", (2, r), (4, r), DARK_GRAY),
                ("FONTNAME", (2, r), (4, r), "Helvetica-Bold"),
            ]
        elif typ == "ph_header":
            sum_styles += [
                ("TEXTCOLOR", (2, r), (4, r), DARK_GRAY),
                ("FONTNAME", (2, r), (4, r), "Helvetica-BoldOblique"),
                ("TOPPADDING", (0, r), (-1, r), 8), 
                ("BOTTOMPADDING", (0, r), (-1, r), 2),
            ]
        elif typ == "ph_item":
            sum_styles += [
                ("TEXTCOLOR", (2, r), (4, r), DARK_GRAY),
                ("FONTSIZE", (0, r), (-1, r), 7.5),
                ("TOPPADDING", (0, r), (-1, r), 1),
                ("BOTTOMPADDING", (0, r), (-1, r), 1),
            ]
        elif typ == "remaining":
            sum_styles += [
                ("TEXTCOLOR", (2, r), (4, r), RED),
                ("FONTNAME", (2, r), (4, r), "Helvetica-Bold"),
                ("TOPPADDING", (0, r), (-1, r), 8),
            ]

    t_sum.setStyle(TableStyle(sum_styles))
    
    # Draw Summary - ZERO GAP
    w_sum, h_sum = t_sum.wrapOn(c, W, H)
    t_sum.drawOn(c, margin, cursor_y_after_table - h_sum) 

    # -------------------------------
    # 5. INFO SECTION (LEFT SIDE)
    # -------------------------------
    
    info_y = cursor_y_after_table - 8 * mm # Jarak dari tabel item
    left_x = margin
    info_w = col_widths[0] + col_widths[1] - 5*mm 

    # Event Details
    if wedding_date or venue:
        info_y = _draw_underlined_header(c, "EVENT DETAILS:", left_x, info_y)
        c.setFont("Helvetica", 9)
        c.setFillColor(BLACK)
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
            info_y -= 8 * mm 
            
    # Payment Info
    info_y = _draw_underlined_header(c, "PAYMENT INFO:", left_x, info_y)
    c.setFont("Helvetica", 8)
    c.setFillColor(BLACK)
    
    c.setFont("Helvetica-Bold", 8)
    c.drawString(left_x, info_y, "Bank:")
    c.setFont("Helvetica", 8)
    c.drawString(left_x + 15*mm, info_y, bank_nm)
    info_y -= 4 * mm
    
    c.setFont("Helvetica-Bold", 8)
    c.drawString(left_x, info_y, "Account:")
    c.setFont("Helvetica", 8)
    c.drawString(left_x + 15*mm, info_y, bank_ac)
    info_y -= 4 * mm
    
    c.setFont("Helvetica-Bold", 8)
    c.drawString(left_x, info_y, "A/N:")
    c.setFont("Helvetica", 8)
    c.drawString(left_x + 15*mm, info_y, bank_an)
    info_y -= 8 * mm

    # Terms & Conditions (Table Layout for Perfect Hanging Indent)
    if terms_text:
        info_y = _draw_underlined_header(c, "TERMS & CONDITIONS:", left_x, info_y)
        
        # Use a table with 2 columns: Number (Fixed) + Text (Dynamic)
        num_col_w = 4 * mm
        text_col_w = info_w - num_col_w
        
        # Recalculate font based on narrower text column
        terms_font_size, terms_leading = _calculate_dynamic_font(terms_text, text_col_w)
        
        t_style = ParagraphStyle(
            'TermsInfo',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=terms_font_size,
            leading=terms_leading,
            textColor=DARK_GRAY,
        )

        lines = [l.strip() for l in terms_text.split('\n') if l.strip()]
        t_data = []
        for i, line in enumerate(lines, 1):
            t_data.append([
                Paragraph(f"{i}.", t_style),
                Paragraph(line, t_style)
            ])
            
        t_terms = Table(t_data, colWidths=[num_col_w, text_col_w])
        t_terms.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        
        _, h_t = t_terms.wrapOn(c, info_w, H)
        t_terms.drawOn(c, left_x, info_y - h_t) 
        info_y -= h_t 

    # =========================================================
    # 6. FOOTER BAR (BLACK)
    # =========================================================
    _draw_footer_contact(c, W)

    # =========================================================
    # 7. PAGE 2: PAYMENT PROOF (Flexible Height)
    # =========================================================
    proof_data = meta.get("payment_proof")
    if proof_data:
        c.showPage() # Flush Page 1
        
        # Helper to load image from base64 or bytes
        try:
            from PIL import Image
            import base64
            
            img_stream = None
            if isinstance(proof_data, str):
                try:
                    if "," in proof_data: proof_data = proof_data.split(",", 1)[1]
                    img_bytes = base64.b64decode(proof_data)
                    img_stream = BytesIO(img_bytes)
                except: pass
            elif isinstance(proof_data, (bytes, bytearray)):
                img_stream = BytesIO(proof_data)
            
            if img_stream:
                img = ImageReader(Image.open(img_stream))
                iw, ih = img.getSize()
                aspect = ih / float(iw)

                # Fixed Width (A4 width - margins)
                draw_w = W - 2*margin
                
                # Calculate needed height
                draw_h = draw_w * aspect
                
                # Calculate needed Page Height
                # If image is tall, extend page. If short, use at least A4.
                header_h = top_bar_h
                needed_H = header_h + draw_h + 2*margin
                
                final_H = max(H, needed_H)
                
                # Resize Page
                c.setPageSize((W, final_H))
                
                # Draw Header (Fixed at top)
                c.setFillColor(BLACK)
                c.rect(0, final_H - header_h, W, header_h, fill=1, stroke=0)
                c.setFillColor(WHITE)
                c.setFont("Times-Bold", 18)
                c.drawRightString(W - margin, final_H - 20 * mm, "PAYMENT PROOF")
                
                _try_draw_logo(c, margin + 2*mm, final_H - header_h + 2*mm, logo_block_w - 4*mm, header_h - 4*mm, "assets/logo.png")
                
                # Draw Image (below header)
                # Bottom Y = Top Y - Image Height
                img_y = final_H - header_h - margin - draw_h
                c.drawImage(img, margin, img_y, width=draw_w, height=draw_h, mask="auto")
                
        except Exception as e:
            # Fallback error on standard page
            c.setPageSize(A4)
            c.setFillColor(colors.red)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(margin, H - 50*mm, f"Error displaying proof: {str(e)}")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf
