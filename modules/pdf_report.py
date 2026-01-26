import io
import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart

from ui.formatters import rupiah

# --- Shared Style Constants & Helpers (Ported from invoice.py) ---

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

def _draw_footer_contact(c, W):
    """Draws footer bar similar to invoice.py"""
    bar_h = 10 * mm
    c.setFillColor(colors.HexColor("#1a1a1a"))
    c.rect(0, 0, W, bar_h, fill=1, stroke=0)
    
    # Hardcoded contact info for consistency
    items = [
        "Jl. Panembakan (Cimahi)",
        "theorbitphoto@gmail.com",
        "0813-2333-1506"
    ]
    
    font_name = "Helvetica"
    font_size = 7
    c.setFillColor(colors.white)
    c.setFont(font_name, font_size)
    
    text = "   |   ".join(items)
    c.drawCentredString(W/2, (bar_h/2) - (font_size/2) + 1, text)

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
    c.setFont("Times-Bold", 20)
    c.drawRightString(W - margin, H - 18 * mm, title_main)


def _page_template(canvas, doc, title):
    """Background template for every page."""
    canvas.saveState()
    _draw_brand_header(canvas, doc, title)
    _draw_footer_contact(canvas, A4[0])
    canvas.restoreState()


def _create_revenue_chart(chart_data: list) -> Drawing:
    """Creates a vertical bar chart for monthly revenue."""
    # 1. Prepare Data (Fill 1-12 months)
    revenue_map = {d['month']: d['revenue'] for d in chart_data}
    data = [tuple(revenue_map.get(m, 0) for m in range(1, 13))]
    
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
    bc.categoryAxis.categoryNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    bc.categoryAxis.labels.boxAnchor = 'n'
    bc.categoryAxis.labels.dy = -10
    
    drawing.add(bc)
    return drawing


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
        client = item.get('client', '-')
        venue = item.get('venue', '-') or '-'
        evt_date = item.get('event_date', item.get('created_date', '-')) # Fallback to created
        # Clean up date format (remove Day Name) to prevent overflow
        # e.g., "Wednesday, 22 April 2026" -> "22 April 2026"
        if evt_date and ',' in evt_date:
            try:
                evt_date = evt_date.split(',')[1].strip()
            except:
                pass

        # Use Paragraphs for text wrapping
        # Invoice column is now wider
        row = [
            Paragraph(inv_no, style_bold),
            Paragraph(venue, style_normal),
            evt_date,
            rupiah(item.get('amount', 0)).replace('Rp ', '')
        ]
        table_data.append(row)
        total_amount += item.get('amount', 0)
        
    # Total Row
    table_data.append(["", "", "TOTAL REVENUE", rupiah(total_amount)])
    
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
        
        # Center the chart
        d = _create_revenue_chart(chart_data)
        elements.append(d)
    
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
