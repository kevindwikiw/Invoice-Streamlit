import streamlit as st
from typing import List, Dict, Any
from modules.utils import safe_float, normalize_desc_text, desc_to_lines, rupiah
from controllers.invoice_callbacks import cb_add_item_to_cart, cb_delete_item_by_row_id
from views.styles import POS_COLUMN_RATIOS
from views.invoice_components import render_package_card

CATEGORIES = [
  "Wedding",
  "Bundling Package",
  "Prewedding",
  "Engagement/Sangjit",
  "Corporate/Event",
  "Add-ons",
  "Free / Complimentary"
]

def render_sidebar_packages_v2(packages: List[Dict[str, Any]]) -> None:
    """Refactored Sidebar: Cleaner, Modular, Limit 5."""
    
    st.markdown('<div class="sidebar-header"><h3>📦 Select Packages</h3></div>', unsafe_allow_html=True)
    st.caption("Browse & Select Multiple Packages")
    if st.button("🌐 Full Catalog", key="btn_full_catalog", use_container_width=True):
        st.session_state["show_catalog"] = not st.session_state.get("show_catalog", False)
        st.rerun()

    # Search (Moved to bottom for alignment)
    search_query = st.text_input("Search", placeholder="🔍 Search...", key="sb_search", label_visibility="collapsed").lower().strip()
    
    # Cart State
    cart_ids = {str(item.get("_row_id")) for item in st.session_state.get("inv_items", [])}
    
    # Filter
    filtered = [p for p in packages if search_query in str(p.get("name", "")).lower()] if search_query else packages
    
    # SORT: 1. Added (Top), 2. High Price to Low
    filtered = sorted(
        filtered, 
        key=lambda x: (str(x.get("id")) in cart_ids, safe_float(x.get("price", 0))), 
        reverse=True
    )
    
    # Grouping
    grouped = {cat: [] for cat in CATEGORIES}
    for p in filtered:
        cat = p.get("category", "Other")
        if cat in grouped:
            grouped[cat].append(p)
            
    if not any(grouped.values()):
        st.caption("No packages found.")
        return

    # Render Categories
    for category in CATEGORIES:
        items = grouped[category]
        if not items: continue
        
        # Limit Logic: Tailored per category
        limit_map = {
            "Wedding": 2,
            "Engagement/Sangjit": 1,
            "Bundling Package": 2,
            "Prewedding": 1,
            "Corporate/Event": 1,
            "Add-ons": 1,
            "Free / Complimentary": 1
        }
        limit = limit_map.get(category, 4) # Default 4 for others (Add-ons, Free)
        
        # Pagination
        page_key = f"pge_{category}"
        if page_key not in st.session_state: st.session_state[page_key] = 0
        current_page = st.session_state[page_key]
        
        if search_query:
            display_items = items; is_paginated = False
        else:
            is_paginated = True
            total = len(items)
            start = current_page * limit
            display_items = items[start : start + limit]
            
            # Auto-reset if empty page
            if not display_items and current_page > 0:
                st.session_state[page_key] = 0; st.rerun()

        # Header (Category + Count)
        count_display = f"{len(display_items)}/{len(items)}"
        
        # Color Map for Categories
        # Color Map for Categories (Synced with views/styles.py .pkg-pill)
        cat_colors = {
            "Wedding": "#fce7f3",             # Pink
            "Bundling Package": "#e0e7ff",    # Indigo
            "Prewedding": "#e0f2fe",          # Sky
            "Engagement/Sangjit": "#ccfbf1",  # Teal
            "Corporate/Event": "#f1f5f9",     # Slate
            "Add-ons": "#fff7ed",             # Orange
            "Free / Complimentary": "#dcfce7" # Green
        }
        bg_color = cat_colors.get(category, "#f8fafc")
        
        # Style: Simpler, closer to Streamlit native
        st.markdown(f'''
            <div style="
                display:flex; justify-content:space-between; align-items:center; 
                margin-top:16px; margin-bottom:8px;
                background:{bg_color}; padding:6px 12px; border-radius:6px;
            ">
                <div style="font-weight:600; font-size:14px; color:#31333F;">
                    {category}
                </div>
                <div style="font-size:12px; color:#64748b; background:rgba(255,255,255,0.6); padding:2px 8px; border-radius:4px;">
                    {count_display}
                </div>
            </div>
        ''', unsafe_allow_html=True)

        # 1-Column List Layout
        for pkg in display_items:
            _render_sidebar_item(pkg, cart_ids)
            
        # UI STABILITY: Spacer for missing items
        if is_paginated:
            missing = limit - len(display_items)
            if missing > 0:
                # Approx 85px per card
                st.markdown(f"<div style='height: {missing * 85}px;'></div>", unsafe_allow_html=True)

        # Pagination Controls
        if is_paginated and len(items) > limit:
            _render_pagination(category, current_page, len(items), limit, page_key)


def _render_sidebar_item_compact(pkg, cart_ids):
    """Compact card for 2-column grid layout using shared render_package_card."""
    pkg_id = str(pkg["id"])
    is_added = pkg_id in cart_ids
    
    # Use the same render_package_card as Package Database for consistent hover
    desc = pkg.get("description", "")
    raw_lines = desc_to_lines(normalize_desc_text(desc))
    lines = raw_lines[:3]
    if len(raw_lines) > 3:
        lines.append(f"... (+{len(raw_lines)-3})")
    
    html_code = render_package_card(
        name=pkg["name"], 
        price=safe_float(pkg["price"]), 
        description=lines,
        category=pkg.get("category"),
        is_added=is_added,
        compact=True,
        rupiah_formatter=rupiah,
        full_description=raw_lines
    )
    st.markdown(html_code, unsafe_allow_html=True)
    
    # Action button
    if is_added:
        st.button("✕", key=f"rem_{pkg_id}", use_container_width=True, on_click=cb_delete_item_by_row_id, args=(pkg_id,))
    else:
        st.button("＋", key=f"add_{pkg_id}", use_container_width=True, on_click=cb_add_item_to_cart, args=(pkg,))


def _render_sidebar_item(pkg, cart_ids):
    pkg_id = str(pkg["id"])
    is_added = pkg_id in cart_ids
    
    # Prepare lines for tooltip/desc
    # Prepare lines for tooltip/desc
    desc = pkg.get("description", "")
    raw_lines = desc_to_lines(normalize_desc_text(desc))
    lines = raw_lines[:3]
    if len(raw_lines) > 3:
        lines.append(f"... (+{len(raw_lines)-3})")
    
    # Layout (Clean)
    c_card, c_btn = st.columns([0.82, 0.18], gap="small", vertical_alignment="center")
    
    with c_card:
        # Render Card HTML (using shared styles)
        html_code = render_package_card(
            name=pkg["name"], 
            price=safe_float(pkg["price"]), 
            description=lines, # Pass list for bullets
            category=pkg.get("category"),
            is_added=is_added,
            compact=True,
            rupiah_formatter=rupiah,
            full_description=raw_lines
        )
        st.markdown(html_code, unsafe_allow_html=True)
        
    with c_btn:
        if is_added:
            # Simple X icon
            st.button("✕", key=f"rem_{pkg_id}", on_click=cb_delete_item_by_row_id, args=(pkg_id,))
        else:
            # Simple + icon
            st.button("＋", key=f"add_{pkg_id}", on_click=cb_add_item_to_cart, args=(pkg,))

def _render_pagination(category, current, total, limit, key):
    # Symmetric Layout: [Btn 25%] [Text 50%] [Btn 25%]
    c1, c2, c3 = st.columns([0.25, 0.50, 0.25], vertical_alignment="center")
    total_pages = (total + limit - 1) // limit
    
    with c1:
        if st.button("‹", key=f"p_{key}_prev", disabled=(current==0), use_container_width=True):
            st.session_state[key] = max(0, current - 1)
            st.rerun()
            
    with c2:
        st.markdown(
            f"<div style='text-align:center; color:#8e8e93; font-size:0.8rem; line-height:2.2;'>{current+1} / {total_pages}</div>", 
            unsafe_allow_html=True
        )
        
    with c3:
        if st.button("›", key=f"p_{key}_next", disabled=(current >= total_pages-1), use_container_width=True):
            st.session_state[key] = current + 1
            st.rerun()



# Removing @st.dialog decorator so it can be embedded in main page
def render_full_catalog_content(packages: List[Dict[str, Any]]):
    """Multi-select catalog with batch apply. Checkbox on top for animation."""
    
    # st.markdown style removed (no longer needed for modal width hack)
    
    # Source of truth
    cart_ids = {str(item.get("_row_id")) for item in st.session_state.get("inv_items", [])}
    
    # Pending state
    if "_pa" not in st.session_state: st.session_state._pa = set()
    if "_pr" not in st.session_state: st.session_state._pr = set()
    pend_add, pend_rem = st.session_state._pa, st.session_state._pr
    
    # Search
    search = st.text_input("🔍 Search...", key="fc_s", label_visibility="collapsed").lower().strip()
    
    # Group O(n)
    grouped = {cat: [] for cat in CATEGORIES}
    for p in packages:
        if search and search not in p.get("name", "").lower(): continue
        cat = p.get("category")
        if cat in grouped: grouped[cat].append(p)
    
    if not any(grouped.values()):
        st.info("No packages found.")
        return
    
    # Color Map (Synced)
    cat_colors = {
        "Wedding": "#fce7f3",             # Pink
        "Bundling Package": "#e0e7ff",    # Indigo
        "Prewedding": "#e0f2fe",          # Sky
        "Engagement/Sangjit": "#ccfbf1",  # Teal
        "Corporate/Event": "#f1f5f9",     # Slate
        "Add-ons": "#fff7ed",             # Orange
        "Free / Complimentary": "#dcfce7" # Green
    }

    # Render
    for cat, items in grouped.items():
        if not items: continue
        
        bg_color = cat_colors.get(cat, "#f8fafc")
        
        st.markdown(f'''
            <div style="
                display:flex; justify-content:space-between; align-items:center; 
                margin-top:24px; margin-bottom:12px;
                background:{bg_color}; padding:8px 16px; border-radius:8px;
            ">
                <div style="font-weight:700; font-size:16px; color:#31333F;">
                    {cat}
                </div>
                <div style="font-size:13px; color:#64748b; background:rgba(255,255,255,0.6); padding:2px 10px; border-radius:6px; font-weight:600;">
                    {len(items)} Items
                </div>
            </div>
        ''', unsafe_allow_html=True)
        
        for i in range(0, len(items), 3):
            cols = st.columns(3)
            for j, pkg in enumerate(items[i:i+3]):
                with cols[j]:
                    pid = str(pkg["id"])
                    in_cart = pid in cart_ids
                    is_sel = (in_cart or pid in pend_add) and pid not in pend_rem
                    
                    # CHECKBOX FIRST (for animation)
                    chk = st.checkbox("" if is_sel else "", value=is_sel, key=f"fc_{pid}")
                    
                    # Update pending
                    if chk and not in_cart: pend_add.add(pid); pend_rem.discard(pid)
                    elif not chk and in_cart: pend_rem.add(pid); pend_add.discard(pid)
                    elif chk and in_cart: pend_rem.discard(pid)
                    elif not chk and not in_cart: pend_add.discard(pid)
                    
                    # Card with CHECKBOX value for instant visual
                    desc_lines_raw = desc_to_lines(normalize_desc_text(pkg.get("description", "")))
                    desc_lines = desc_lines_raw[:3]
                    if len(desc_lines_raw) > 3:
                        desc_lines.append(f"... (+{len(desc_lines_raw)-3})")
                        
                    html = render_package_card(pkg["name"], safe_float(pkg["price"]), desc_lines, 
                                               pkg.get("category"), is_added=chk, compact=False, 
                                               rupiah_formatter=rupiah, full_description=desc_lines_raw)
                    st.markdown(html, unsafe_allow_html=True)
        st.markdown("---")
    
    # Summary & Apply
    net = len(cart_ids) + len(pend_add) - len(pend_rem)
    if pend_add or pend_rem:
        st.info(f"+{len(pend_add)} / -{len(pend_rem)} → **{net}** total")
    
    if st.button("✓ Apply & Close", type="primary", use_container_width=True):
        pkg_map = {str(p["id"]): p for p in packages}
        for pid in pend_add:
            if pid in pkg_map: cb_add_item_to_cart(pkg_map[pid])
        for pid in pend_rem:
            cb_delete_item_by_row_id(pid)
        st.session_state._pa = set()
        st.session_state._pr = set()
        st.session_state["show_catalog"] = False
        st.rerun()

