import streamlit as st
from typing import List, Dict, Any
from modules.utils import safe_float, normalize_desc_text, desc_to_lines, rupiah
from controllers.invoice_callbacks import cb_add_item_to_cart, cb_delete_item_by_row_id
from views.styles import POS_COLUMN_RATIOS
from views.invoice_components import render_package_card

CATEGORIES = ["Utama", "Bonus", "Add-on"]

def render_sidebar_packages_v2(packages: List[Dict[str, Any]]) -> None:
    """Refactored Sidebar: Cleaner, Modular, Limit 5."""
    
    st.markdown('<div class="sidebar-header"><h3>📦 Select Packages</h3></div>', unsafe_allow_html=True)
    
    # Search
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
        
        # Limit Logic (Utama: 7, Others: 3 = Total 10)
        limit = 7 if category == "Utama" else 3
        
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
        st.markdown(f'''
            <div style="display:flex; justify-content:space-between; align-items:flex-end; margin-top:12px;">
                <div class="sidebar-category" style="margin:0; border:none;">{category}</div>
                <div style="font-size:0.7rem; color:#9ca3af;">{count_display}</div>
            </div>
            <hr style="margin:4px 0 8px 0; border-top:1px solid #eee;">
        ''', unsafe_allow_html=True)

        # List Items Loop
        for pkg in display_items:
            _render_sidebar_item(pkg, cart_ids)
            
        # UI STABILITY: Spacer logic
        if is_paginated:
            missing = limit - len(display_items)
            if missing > 0:
                # 85px is approx height of 1 card row
                st.markdown(f"<div style='height: {missing * 85}px;'></div>", unsafe_allow_html=True)

        # Pagination Controls
        if is_paginated and len(items) > limit:
            _render_pagination(category, current_page, len(items), limit, page_key)


def _render_sidebar_item(pkg, cart_ids):
    pkg_id = str(pkg["id"])
    is_added = pkg_id in cart_ids
    
    # Prepare lines for tooltip/desc
    desc = pkg.get("description", "")
    lines = desc_to_lines(normalize_desc_text(desc))
    
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
            rupiah_formatter=rupiah
        )
        st.markdown(html_code, unsafe_allow_html=True)
        
    with c_btn:
        if is_added:
            # Simple X icon
            if st.button("✕", key=f"rem_{pkg_id}"):
                cb_delete_item_by_row_id(pkg_id)
                st.rerun()
        else:
            # Simple + icon
            if st.button("＋", key=f"add_{pkg_id}"):
                cb_add_item_to_cart(pkg)
                st.rerun()

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
