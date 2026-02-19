import streamlit as st
from typing import List

POS_COLUMN_RATIOS = [2.2, 0.8, 0.6, 1.2, 0.5]  # Description | Price | Qty | Total | Del

def _pos_grid_template(ratios: List[float]) -> str:
    return " ".join([f"{r}fr" for r in ratios])

@st.cache_data(show_spinner=False)
def get_invoice_css() -> str:
    """Returns CSS styles for the invoice view."""
    grid = _pos_grid_template(POS_COLUMN_RATIOS)
    return f"""
    <style>
    /* --- FONT PERFORMANCE: swap injected via JS below --- */

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
    
    /* Mobile Responsive Utilities */
    @media (max-width: 640px) {{
        .mobile-hidden {{ display: none !important; }}
        .desktop-hidden {{ display: block !important; }}
    }}
    
    .sidebar-header h3 {{
        font-size: 1rem !important;
        font-weight: 700 !important;
        color: #1f2937 !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    .sidebar-header {{
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid #f3f4f6;
    }}

    /* --- ISO COMPONENTS (Cards & Badges) --- */
    /* --- UNIFIED CARD COMPONENT --- */
    /* --- UNIFIED CARD COMPONENT --- */
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

    /* Base Card (Catalog & Sidebar) */
    .pkg-card {{
        background: #fff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 14px;
        transition: all 0.2s ease;
        position: relative;
        height: 100%;
    }}
    .pkg-card:hover {{
        border-color: #cbd5e1;
        box-shadow: 0 8px 20px rgba(0,0,0,0.08);
        transform: translateY(-2px);
    }}
    
    /* State: Added */
    .pkg-card.added {{
        background: #f0fdf4;
        border-color: #86efac;
    }}
    .pkg-card.added:hover {{
        border-color: #4ade80;
    }}

    /* Variant: Compact (Sidebar) */
    /* Variant: Compact (Sidebar) */
    .pkg-card.compact {{
        padding: 6px 0;
        margin: 4px 0;
        border-radius: 0;
        box-shadow: none !important;
        background: transparent !important;
        border: none !important;
        border-bottom: 1px solid #f3f4f6 !important;
    }}
    .pkg-card.compact:hover {{
        background: transparent !important;
        box-shadow: none !important;
        /* opacity: 0.8; REMOVED to prevent tooltip transparency/ghosting */
    }}
    
    /* FIX: Restore Green Background for Added items (Universal) */
    .pkg-card.added {{
        background: #f0fdf4 !important;
        border: 1px solid #10b981 !important; /* Full border for grid cards */
    }}
    
    /* Specific overrides for Sidebar (Compact) */
    .pkg-card.compact.added {{
        border: 1px solid #e5e7eb !important; /* Reset full border */
        border-left: 3px solid #10b981 !important; /* Left accent only */
        border-bottom: 1px solid #10b981 !important; 
        padding-left: 10px; 
        margin-left: -5px;
    }}

    /* Elements */
    .pkg-title {{
        font-weight: 700;
        font-size: 0.95rem;
        color: #1f2937;
        line-height: 1.3;
        margin-bottom: 4px;
    }}
    .pkg-price {{
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-weight: 700;
        font-size: 0.9rem;
        color: #059669;
        margin-bottom: 6px;
    }}
    /* Tooltip/Popover CSS for Sidebar Description */
    .pkg-desc {{
        font-size: 0.8rem;
        color: #9ca3af; /* Lighter gray (Sepian) */
        line-height: 1.4;
        margin-top: 4px;
        font-weight: 400;
        min-height: 4.5em; /* FIX: Force height for 3 lines (1.4em * 3 approx) */
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }}
    
    /* Strict Sidebar Height */
    .pkg-card.compact .pkg-desc {{
        font-size: 0.75rem;
        height: 2.8em; /* Force fixed height */
        min-height: 2.8em;
        -webkit-line-clamp: 2;
        pointer-events: none; /* KILL NATIVE BROWSER TOOLTIP */
    }}
    
    /* HOVER STATE: Expand over content */
    /* We target the specific card hover */
    /* REMOVED .pkg-card.compact:hover .pkg-desc to avoid double hover effect.
       We rely solely on .pkg-tip (Rich Tooltip) now. */ 
    
    /* Ensure card container doesn't clip */
    .pkg-card.compact {{ overflow: visible !important; }}

    /* Badges / Pills */
    .pkg-pill {{
        font-size: 0.65rem;
        font-weight: 800;
        padding: 2px 8px;
        border-radius: 999px;
        display: inline-block;
        margin-bottom: 6px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    /* Category Colors */
    .pkg-pill.cat-wedding {{ background: #fce7f3; color: #be185d; border: 1px solid #fbcfe8; }}       /* Pink */
    .pkg-pill.cat-bundling {{ background: #e0e7ff; color: #4338ca; border: 1px solid #c7d2fe; }}      /* Indigo/Purple */
    .pkg-pill.cat-prewedding {{ background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; }}    /* Sky */
    .pkg-pill.cat-engagement {{ background: #ccfbf1; color: #0f766e; border: 1px solid #99f6e4; }}    /* Teal */
    .pkg-pill.cat-corporate {{ background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; }}     /* Slate */
    .pkg-pill.cat-addons {{ background: #fff7ed; color: #c2410c; border: 1px solid #ffedd5; }}        /* Orange */
    .pkg-pill.cat-free {{ background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }}          /* Green */
    
    .pkg-pill.main {{ background: #e8f5e9; color: #15803d; }}  /* Fallback */
    .pkg-pill.addon {{ background: #fff7ed; color: #c2410c; }} /* Fallback */
    
    .pkg-badge-added {{
        font-size: 0.75rem;
        color: #10b981;
        font-weight: 700;
        margin-left: 6px;
    }}

    /* Tooltips */
    .pkg-tip {{
        display: none;
        position: absolute;
        left: 0; right: 0; bottom: 100%;
        background: #fff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 12px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        z-index: 50;
        margin-bottom: 10px;
        font-size: 0.8rem;
        color: #4b5563;
    }}
    .pkg-card:hover .pkg-tip {{ display: block; }}
    
    /* Sidebar Specific Headers */
    .sidebar-header {{
        padding: 0.75rem 0;
        border-bottom: 2px solid #e2e8f0;
        margin-bottom: 1rem;
    }}
    .sidebar-header h3 {{
        margin: 0; font-size: 1.1rem; color: #1f2937; font-weight: 600;
    }}
    .sidebar-category {{
        font-size: 0.75rem; font-weight: 700; color: #9ca3af;
        text-transform: uppercase; letter-spacing: 0.08em;
        margin: 1.25rem 0 0.5rem 0; padding-bottom: 0.3rem;
        border-bottom: 1px solid #e5e7eb;
    }}
    
    /* Sticky Bottom Action Bar */
    /* Sticky Bottom Action Bar */
    .sticky-bottom-actions {{
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: white;
        padding: 1rem 2rem;
        border-top: 1px solid #e5e7eb;
        box-shadow: 0 -4px 6px -1px rgba(0, 0, 0, 0.1);
        z-index: 99999;
        display: flex;
        justify-content: flex-end;
        align-items: center;
        gap: 1rem;
        /* Ensure it covers main content area but respects sidebar interaction if possible */
        /* Streamlit structure is complex; fixed bottom usually spans full width */
    }}
    
    /* Adjust for sidebar width if expanded? 
       Streamlit classes are unstable. safer to use right-aligned container 
       or just max-width wrapper/container. 
    */
    /* Better approach: Target a specific container ID if possible, but class is easier. */
    
    /* Force Dialog Width for Large Modals */
    div[data-testid="stDialog"] > div[role="dialog"] {{
        width: 80vw !important;
        max-width: 1000px !important;
    }}
    
    /* Custom Input Labels */
    .label-standard, .label-required, .label-optional {{
        font-family: "Source Sans Pro", sans-serif;
        font-size: 14px; 
        margin-bottom: 0.5rem; /* Match Streamlit Gap */
        display: block;
    }}

    .label-required {{
        color: #31333F; /* Streamlit Default Text */
        font-weight: 400; /* Standard Weight */
    }}
    .label-required::after {{
        content: " *";
        color: #ff4b4b; /* Streamlit Red */
    }}
    
    .label-optional {{
        color: #31333F;
        font-weight: 400;
    }}
    .label-optional span {{
        font-size: 12px;
        color: #808495;
        background: #f0f2f6;
        padding: 2px 6px;
        border-radius: 4px;
        margin-left: 4px;
        vertical-align: middle;
    }}

    .label-standard {{
        color: #31333F;
        font-weight: 400;
    }}
    </style>
    """

def inject_styles() -> None:
    st.markdown(get_invoice_css(), unsafe_allow_html=True)
    # JS: Patch Streamlit's @font-face to use font-display: swap (saves ~600ms)
    st.markdown("""<script>
(function(){try{for(var i=0;i<document.styleSheets.length;i++){try{var rules=document.styleSheets[i].cssRules||[];for(var j=0;j<rules.length;j++){if(rules[j].type===5&&rules[j].style.fontFamily&&rules[j].style.fontFamily.indexOf('Material')!==-1){rules[j].style.fontDisplay='swap';}}}catch(e){}};}catch(e){}})();
</script>""", unsafe_allow_html=True)


# ==============================================================================
# UI COMPONENTS (Moved from ui/components.py)
# ==============================================================================
import html
import textwrap
from contextlib import contextmanager
from typing import Optional

def _next_key(prefix: str) -> str:
    """Generate a unique key per session (anti duplicate key)."""
    st.session_state.setdefault("_ui_seq", 0)
    st.session_state["_ui_seq"] += 1
    return f"{prefix}_{st.session_state['_ui_seq']}"


def page_header(title: str, subtitle: str | None = None):
    """Consistent page title + subtitle (match theme.py)."""
    st.markdown(f"<h1 class='page-title'>{title}</h1>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(f"<div class='page-subtitle'>{subtitle}</div>", unsafe_allow_html=True)


def section(title: str):
    st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)


def col_header(text: str):
    st.markdown(f"<div class='col-header'>{text}</div>", unsafe_allow_html=True)


def danger_container(key: Optional[str] = None):
    """
    Container wrapper untuk styling tombol danger.
    Key otomatis unik biar nggak StreamlitDuplicateElementKey.
    Theme kamu target selector data-key^="danger".
    """
    if not key:
        key = _next_key("danger")
    if not str(key).startswith("danger"):
        key = f"danger_{key}"
    return st.container(key=key)


@contextmanager
def muted_container():
    with st.container():
        st.markdown("<div style='color: var(--muted)'>", unsafe_allow_html=True)
        try:
            yield
        finally:
            st.markdown("</div>", unsafe_allow_html=True)


def render_package_card(
    name: str,
    price: float,
    description: str | list = "",
    category: str = "",
    is_added: bool = False,
    is_main: bool = False,
    compact: bool = False,
    desc_max_lines: int = 2,
    rupiah_formatter=None,
    full_description: list | None = None
) -> str:
    """
    Generates HTML for a package card.
    Supports description as String (legacy) or List (bullets).
    """
    
    # Safe text
    safe_name = html.escape(str(name or "Unnamed"))
    
    # Handle Description (List vs String)
    # For compact view, limit to 3 lines max
    max_lines = 3 if compact else 10
    
    if isinstance(description, list):
        lines_filtered = [line for line in description if line.strip()]
        # Limit lines for display (truncate with ...)
        if len(lines_filtered) > max_lines:
            display_lines = lines_filtered[:max_lines]
            display_lines[-1] = display_lines[-1] + " ..."
        else:
            display_lines = lines_filtered
            
        if full_description:
            # Use provided full list for tooltip
            desc_text_for_title = "\n".join([f"• {line}" for line in full_description if line.strip()])
        else:
            # Use the filtered list (might be truncated already if caller passed truncated)
            # This is fallback. Ideally caller passes full_description if they truncate 'description'
            desc_text_for_title = "\n".join([f"• {line}" for line in lines_filtered])
            
        # Truncated for card display (already truncated by caller if passed as list usually, or we truncate here)
        safe_desc = "<br>".join([f"• {html.escape(line)}" for line in display_lines])
    else:
        desc_text = str(description or "")
        desc_text_for_title = str(full_description) if full_description else desc_text
        # Limit string by lines too
        lines = desc_text.split("\n")
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = lines[-1] + " ..."
        safe_desc = "<br>".join([f"• {html.escape(line)}" for line in lines if line.strip()])
    
    # Price formatting
    price_str = rupiah_formatter(price) if rupiah_formatter else f"Rp {price:,.0f}".replace(",", ".")
    
    # Classes
    card_classes = ["pkg-card"]
    if compact:
        card_classes.append("compact")
    if is_added:
        card_classes.append("added")
        
    class_str = " ".join(card_classes)
    
    # Pill (only if not compact)
    pill_html = ""
    if not compact and category:
        cat_map = {
            "Wedding": "cat-wedding",
            "Bundling Package": "cat-bundling",
            "Prewedding": "cat-prewedding",
            "Engagement/Sangjit": "cat-engagement",
            "Corporate/Event": "cat-corporate",
            "Add-ons": "cat-addons",
            "Free / Complimentary": "cat-free"
        }
        pill_class = cat_map.get(category, "main" if is_main else "addon")
        pill_html = f'<span class="pkg-pill {pill_class}">{html.escape(category)}</span>'
        
    # Added Badge (inline in title)
    badge_html = ""
    if is_added:
        badge_html = '<span class="pkg-badge-added">✓ Added</span>'
        
    # Description Logic
    # 1. Compact View (Sidebar): Fixed 2 lines.
    # 2. Tooltip: Hovering card shows full details in a nice bubble above.
    
    # Native title backup (simple) - Removed to rely on pointer-events:none
    # desc_html = f'<div class="pkg-desc" title="">{safe_desc}</div>'
    desc_html = f'<div class="pkg-desc">{safe_desc}</div>'

    # Rich HTML Tooltip (The "Best Hover")
    # Positioned by CSS .pkg-tip (bottom: 100% -> appears above card)
    tooltip_html = ""
    if safe_desc:
        tooltip_inner = f"""
            <div class="pkg-tip">
                <div style="font-weight:700; margin-bottom:4px; color:#1f2937;">📋 Details</div>
                {html.escape(desc_text_for_title).replace(chr(10), "<br>")}
            </div>
        """
        tooltip_html = tooltip_inner

    # Construct final HTML
    html_parts = [
        f'<div class="{class_str}">',
        tooltip_html, # Tooltip sits inside card, absolute positioned relative to card
        pill_html,
        f'<div class="pkg-title">{safe_name}{badge_html}</div>',
        f'<div class="pkg-price">{price_str}</div>',
        desc_html,
        '</div>'
    ]

    
    return "".join(html_parts)
