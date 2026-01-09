import streamlit as st
from typing import List

POS_COLUMN_RATIOS = [2.4, 0.6, 2, 0.7]  # Description | Qty | Total | Del

def _pos_grid_template(ratios: List[float]) -> str:
    return " ".join([f"{r}fr" for r in ratios])

def get_invoice_css() -> str:
    """Returns CSS styles for the invoice view."""
    grid = _pos_grid_template(POS_COLUMN_RATIOS)
    return f"""
    <style>
    /* --- UTILITIES --- */
    .hrow {{ display:flex; gap:10px; align-items:center; justify-content:space-between; }}
    .muted {{ color:#6b7280; font-size:.85rem; }}
    .pill {{ font-size:.72rem; font-weight:900; padding:2px 10px; border-radius:999px; display:inline-block; }}
    .statusbar {{
        display:flex; align-items:center; justify-content:space-between; gap:10px; padding:10px 12px;
        border-radius:12px; border:1px solid rgba(0,0,0,.06); background:#f9fafb;
    }}
    .status-title {{ font-weight:900; color:#111827; font-size:.85rem; letter-spacing:.01em; }}
    .status-right {{ display:flex; align-items:center; gap:8px; }}

    /* --- ISO COMPONENTS (Cards & Badges) --- */
    .iso-card {{
        background-color: white;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        transition: box-shadow 0.2s;
    }}
    .iso-card:hover {{
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-color: #d1d5db;
    }}
    .iso-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}
    .iso-meta {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        color: #6b7280;
        font-size: 0.85rem;
    }}
    .iso-badg {{
         display: inline-flex;
         align-items: center;
         padding: 2px 8px;
         border-radius: 999px;
         font-size: 0.7rem;
         font-weight: 600;
         text-transform: uppercase;
         letter-spacing: 0.05em;
    }}
    .badg-green {{ background: #dcfce7; color: #166534; }}
    .badg-orange {{ background: #ffedd5; color: #9a3412; }}
    .badg-red {{ background: #fee2e2; color: #991b1b; }}
    .badg-blue {{ background: #eef2ff; color: #3730a3; }}

    /* --- SECTION TITLES --- */
    .blk-title {{
        font-size:1.02rem; font-weight:900; color:#111827;
        line-height:1.2; margin:0 0 10px 0;
    }}
    .blk-sub {{ font-size:.82rem; color:#6b7280; margin-top:-6px; margin-bottom:10px; }}

    /* --- CATALOG CARD --- */
    .card {{
        background:#fff; border:1px solid #e5e7eb; border-radius:14px; padding:14px;
        transition:.15s ease; position:relative; height:100%;
        overflow: visible;
    }}
    .card:hover {{ border-color:#cbd5e1; box-shadow:0 10px 22px rgba(0,0,0,.07); transform:translateY(-2px); }}
    .title {{ font-weight:900; font-size:.95rem; color:#111827; line-height:1.25; margin-top:6px; }}
    .price {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-weight:900; color:#2563eb; margin-top:2px; }}
    .desc {{
        font-size:.82rem; color:#6b7280; margin-top:6px; line-height:1.45;
        display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; min-height:36px;
    }}
    .tip {{
        display:none; position:absolute; left:0; right:0; bottom:100%;
        background:#fff; border:1px solid #e5e7eb; border-radius:14px; padding:12px;
        box-shadow:0 14px 30px rgba(0,0,0,.12); z-index:30; margin-bottom:10px; font-size:.82rem;
    }}
    .card:hover .tip {{ display:block; }}

    /* --- POS TABLE --- */
    .pos-head {{
        display:grid; grid-template-columns:{grid};
        gap:10px; align-items:center; font-size:.72rem; font-weight:900; color:#9ca3af;
        text-transform:uppercase; letter-spacing:.05em; padding:0 0 10px 0;
        border-bottom:1px solid #eee; margin-bottom:8px;
    }}
    .row {{ border-bottom:1px solid #f3f4f6; padding:10px 0; }}
    .it {{ font-weight:900; color:#111827; font-size:.92rem; line-height:1.25; }}
    .meta {{ font-size:.78rem; color:#9ca3af; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
    .tot {{ text-align:right; font-variant-numeric: tabular-nums; font-weight:950; color:#111827; font-size:1.02rem; }}

    /* --- GRAND TOTAL BOX --- */
    .grand {{
        background:#f9fafb; border:1px solid rgba(0,0,0,.06); border-radius:14px;
        padding:14px; text-align:right; margin-top:12px;
    }}
    .grand .lbl {{ font-size:.75rem; font-weight:900; color:#6b7280; text-transform:uppercase; letter-spacing:.05em; }}
    .grand .val {{ font-size:1.65rem; font-weight:950; color:#111827; margin-top:2px; }}

    /* --- WIDGET OVERRIDES --- */
    div[data-testid="stNumberInput"] {{ min-width:0!important; width:100%!important; }}
    div[data-testid="stNumberInput"] input {{ height:2.1rem!important; text-align:center; font-weight:800; padding:0 .25rem!important; }}
    div[data-testid="stButton"] button {{ padding:.28rem .55rem; min-height:0; }}
    </style>
    """

def inject_styles() -> None:
    st.markdown(get_invoice_css(), unsafe_allow_html=True)
