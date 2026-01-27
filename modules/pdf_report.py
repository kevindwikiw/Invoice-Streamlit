import io
import os
from datetime import date, datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from ui.formatters import rupiah

def _parse_month(val):
    """Return month as int 1..12 or None."""
    if val is None:
        return None

    # date/datetime
    if isinstance(val, (date, datetime)):
        return int(val.month)

    # numeric already
    if isinstance(val, (int, float)):
        try:
            m = int(val)
            return m if 1 <= m <= 12 else None
        except: return None

    # strings: "04", "2026-04", "Apr", "April"
    s = str(val).strip()
    if not s:
        return None

    # try patterns like YYYY-MM or YYYY/MM
    for sep in ("-", "/"):
        parts = s.split(sep)
        if len(parts) >= 2:
            if parts[0].isdigit() and len(parts[0]) == 4: # Year first
                try: 
                   m = int(parts[1])
                   return m if 1 <= m <= 12 else None
                except: pass

    # try pure digit string
    if s.isdigit():
        m = int(s)
        return m if 1 <= m <= 12 else None

    # month names
    months_map = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }
    key = s.lower()
    # allow "Apr 2026"
    key = key.split()[0]
    return months_map.get(key)


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

def _draw_footer_contact(c, W, items=None):
    """Draws footer bar with PNG icons and text."""
    import os
    from reportlab.lib.utils import ImageReader
    
    bar_h = 10 * mm
    c.setFillColor(colors.HexColor("#1a1a1a"))
    c.rect(0, 0, W, bar_h, fill=1, stroke=0)
    
    # Icon mapping: keyword in text -> PNG filename
    icon_map = {
        "jl.": "Location.png",
        "panembakan": "Location.png",
        "@gmail": "Email.png",
        "email": "Email.png", 
        "@theorbitphoto": "IG.png",
        "instagram": "IG.png",
        "0813": "Phonecall.png",
        "phone": "Phonecall.png",
        "hp": "Phonecall.png",
    }
    
    # Assets folder path
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
    
    if not items:
        # Default fallback (plain text, no emoji)
        items = [
            "Jl. Panembakan Gg Sukamaju 15 No. 3, Kota Cimahi",
            "theorbitphoto@gmail.com",
            "@theorbitphoto",
            "0813-2333-1506"
        ]
    
    # Font setup
    font_name = "Helvetica"
    font_size = 7
    icon_size = 3.5 * mm  # Size of PNG icons
    icon_spacing = 1.5 * mm  # Space between icon and text
    sep_str = "   |   "
    
    c.setFont(font_name, font_size)
    sep_w = c.stringWidth(sep_str, font_name, font_size)
    
    # Helper: Match item text to icon file
    def get_icon_for_item(text):
        text_lower = text.lower()
        for keyword, icon_file in icon_map.items():
            if keyword.lower() in text_lower:
                icon_path = os.path.join(assets_dir, icon_file)
                if os.path.exists(icon_path):
                    return icon_path
        return None
    
    # Strip emojis from text (if user's DB still has them)
    def clean_text(text):
        # Remove common emoji unicode ranges or just the first char if it's emoji-like
        import re
        # Simple approach: remove everything that's not ASCII-printable or common unicode letters
        cleaned = re.sub(r'^[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF\ufffd]+\s*', '', text)
        return cleaned.strip()
    
    # Prepare items: (icon_path, clean_text, text_width)
    prepared_items = []
    for item_text in items:
        cleaned = clean_text(item_text)
        icon_path = get_icon_for_item(cleaned)
        text_w = c.stringWidth(cleaned, font_name, font_size)
        # Total width: icon + spacing + text (if icon exists)
        item_w = text_w
        if icon_path:
            item_w += icon_size + icon_spacing
        prepared_items.append((icon_path, cleaned, item_w))
    
    # Calculate total width (all items + separators)
    total_w = sum(item[2] for item in prepared_items)
    if len(prepared_items) > 1:
        total_w += sep_w * (len(prepared_items) - 1)
    
    # Drawing
    y_baseline = 4.0 * mm
    y_icon = (bar_h - icon_size) / 2  # Center icon vertically
    cur_x = (W - total_w) / 2
    
    c.setFillColor(colors.white)
    c.setFont(font_name, font_size)
    
    for i, (icon_path, text, item_w) in enumerate(prepared_items):
        # Draw icon if exists
        if icon_path:
            try:
                c.drawImage(icon_path, cur_x, y_icon, width=icon_size, height=icon_size, mask='auto')
                cur_x += icon_size + icon_spacing
            except Exception as e:
                print(f"[Footer] Icon draw error: {e}")
        
        # Draw text
        c.drawString(cur_x, y_baseline, text)
        cur_x += c.stringWidth(text, font_name, font_size)
        
        # Draw separator
        if i < len(prepared_items) - 1:
            c.drawString(cur_x, y_baseline, sep_str)
            cur_x += sep_w

def _draw_brand_header(c, doc, title_main):
    """Draws the Black Brand Header on canvas."""
    W, H = A4
    margin = 15 * mm
    top_bar_h = 25 * mm
    logo_block_w = 50 * mm
    ribbon_drop = 12 * mm
    
    BLACK = colors.HexColor("#1a1a1a")
    WHITE = colors.white

    # 1. Top Bar Background
    c.setFillColor(BLACK)
    c.rect(0, H - top_bar_h, W, top_bar_h, fill=1, stroke=0)
    
    # 2. Logo Area
    _try_draw_logo(c, margin, H - top_bar_h + 2*mm, logo_block_w - 4*mm, top_bar_h - 4*mm, "assets/logo.png")
    
    # Separator Line
    c.setStrokeColor(WHITE)
    c.setLineWidth(0.5)
    c.line(margin + logo_block_w, H - top_bar_h, margin + logo_block_w, H)

    # 3. Ribbon Tail
    tail_pts = [
        (margin, H - top_bar_h),                      
        (margin + logo_block_w, H - top_bar_h),       
        (margin, H - top_bar_h - ribbon_drop)         
    ]
    _draw_polygon(c, tail_pts, fill_color=BLACK, stroke=0)
    
    # White accent lines on triangle
    c.setStrokeColor(WHITE)
    c.setLineWidth(0.5)
    c.line(tail_pts[1][0], tail_pts[1][1], tail_pts[2][0], tail_pts[2][1])
    c.line(margin, H, margin, H - top_bar_h - ribbon_drop)

    # 4. Title
    c.setFillColor(WHITE)
    c.setFont("Times-Bold", 22)
    # Centered Vertical alignment with Logo: Bar center is H-12.5mm
    c.drawRightString(W - margin, H - 16 * mm, title_main)

    # Underline (Matching Invoice Style)
    title_width = c.stringWidth(title_main, "Times-Bold", 22)
    c.setLineWidth(1)
    c.line(W - margin - title_width, H - 18 * mm, W - margin, H - 18 * mm)


def _page_template(canvas, doc, title):
    """Background template for every page."""
    canvas.saveState()
    _draw_brand_header(canvas, doc, title)
    _draw_footer_contact(canvas, A4[0])
    canvas.restoreState()


def _create_revenue_chart(chart_data: list) -> Drawing:
    """Creates a vertical bar chart for monthly revenue."""
    try:
        # Build revenue_map with SUM per month (Aggregate logic)
        revenue_map = {m: 0.0 for m in range(1, 13)}

        for d in (chart_data or []):
            try:
                m = _parse_month(d.get("month"))
                if not m:
                    continue

                rev = d.get("revenue")
                rev = float(rev or 0)

                revenue_map[m] += rev
            except:
                continue

        # Create tuple of 12 months data
        data = [tuple(revenue_map[m] for m in range(1, 13))]
        
        # 2. Setup Chart
        drawing = Drawing(450, 200)
        bc = VerticalBarChart()
        bc.x = 30
        bc.y = 30
        bc.height = 150
        bc.width = 400
        bc.data = data
        bc.strokeColor = colors.white
        
        # Styling
        bc.bars[0].fillColor = colors.HexColor("#16a34a") # Green
        
        # Axis
        bc.valueAxis.valueMin = 0
        
        max_val = max(data[0]) if data and data[0] else 0
        if max_val <= 0:
            bc.valueAxis.valueMax = 100 # Default
        else:
            # Round up logic: e.g. 450 -> 500, 12000 -> 13000
            try:
                digits = len(str(int(max_val)))
                step = 10 ** (digits - 1) if digits > 1 else 10
                bc.valueAxis.valueMax = ((int(max_val) + step - 1) // step) * step
            except:
                bc.valueAxis.valueMax = max_val * 1.1 # Fallback
        
        bc.categoryAxis.categoryNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        bc.categoryAxis.labels.boxAnchor = 'n'
        bc.categoryAxis.labels.dy = -10
        
        drawing.add(bc)
        # Debug helper: if total revenue > 0 but chart looks empty?
        # Maybe valueMin/Max issue. But valueMin=0. Should be fine.
        return drawing
    except Exception as e:
        # Fallback if chart fails: Return empty drawing with error text (Using String shape!)
        d = Drawing(400, 50)
        d.add(String(10, 20, f"Chart Error: {str(e)}", fontName="Helvetica", fontSize=9))
        return d


def _build_report(data: list, title: str, chart_data: list = None) -> io.BytesIO:
    """Core function to build the PDF report."""
    buffer = io.BytesIO()
    
    # Margins need to accommodate the custom header which takes ~30-40mm
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=45*mm, # increased for header
        bottomMargin=20*mm
    )
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Styles for Table
    style_normal = styles["Normal"]
    style_normal.fontSize = 8
    style_normal.leading = 10
    
    style_bold = ParagraphStyle("p_bold", parent=style_normal, fontName="Helvetica-Bold")
    
    # --- Metadata ---
    date_gen = datetime.now().strftime("%d %B %Y")
    elements.append(Paragraph(f"<b>Report Generated:</b> {date_gen}", style_normal))
    elements.append(Spacer(1, 10))
    
    # --- Table Data ---
    # Header: Invoice # | Venue | Event Date | Amount (Adjusted per user Feedback)
    headers = ["Invoice #", "Venue", "Event Date", "Amount"]
    table_data = [headers]
    
    total_amount = 0
    
    for item in data:
        inv_no = item.get('invoice_no', '-')
        # Client removed as requested
        venue = item.get('venue', '-') or '-'
        
        # 4) Date Safety
        evt_date = item.get('event_date') or item.get('created_date') or '-'
        if isinstance(evt_date, (date, datetime)):
            evt_date = evt_date.strftime("%d %B %Y")
        else:
            evt_date = str(evt_date)
            # Clean up comma format if string
            if ',' in evt_date:
                try:
                    evt_date = evt_date.split(',')[1].strip()
                except: pass

        # Safe amount
        amt = float(item.get('amount') or 0)
        
        # Use Paragraphs for text wrapping
        # Invoice column is now wider
        row = [
            Paragraph(inv_no, style_bold),
            Paragraph(venue, style_normal),
            evt_date,
            rupiah(amt).replace('Rp ', '')
        ]
        table_data.append(row)
        total_amount += amt
        
    # Total Row (Consistent Formatting)
    table_data.append(["", "", "TOTAL REVENUE", rupiah(total_amount).replace('Rp ', '')])
    
    # --- Table Styling ---
    # Col Widths: 4 cols. A4 width=210mm. Margins=30mm total. Usable=180mm.
    # New Layout: [60mm, 50mm, 35mm, 35mm]
    col_widths = [60*mm, 50*mm, 35*mm, 35*mm]
    
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1a1a1a")), # Header Black
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'), # Amount aligned right
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        
        # Total Row
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#f3f4f6")),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.black),
        ('TOPPADDING', (0, -1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 25))

    # --- CHART SECTION (Bottom) ---
    if chart_data:
        elements.append(Paragraph("<b>Revenue Trend</b>", style_bold))
        elements.append(Spacer(1, 10))
        
        # 5) Center the chart using Table
        d = _create_revenue_chart(chart_data)
        chart_table = Table([[d]], colWidths=[doc.width], rowHeights=[200]) # Use doc.width for perfect centering
        chart_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(chart_table)
    
    # Build with Callback for Header/Footer
    def on_page(canvas, doc):
        _page_template(canvas, doc, title)
        
    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)
    buffer.seek(0)
    return buffer


def generate_monthly_report(data: list, year: int, month: int) -> io.BytesIO:
    month_name = datetime(2000, month, 1).strftime('%B')
    title = f"MONTHLY REPORT: {month_name.upper()} {year}"
    return _build_report(data, title)

def generate_yearly_report(data: list, year: int, chart_data: list = None) -> io.BytesIO:
    title = f"YEARLY REPORT: {year}"
    return _build_report(data, title, chart_data=chart_data)
