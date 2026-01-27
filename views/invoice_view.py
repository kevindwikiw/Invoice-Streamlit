import streamlit as st
from datetime import datetime
from modules.utils import safe_float, calculate_totals
from modules.utils import safe_float, calculate_totals
from modules.invoice_state import initialize_session_state, load_packages_cached, get_package_version_cached
from views.styles import inject_styles, page_header
from views.invoice_components import (
    render_event_metadata,
    render_pos_section,
    render_payment_section,
    render_action_buttons,
    render_download_section
)
from views.sidebar_components import render_sidebar_packages_v2, render_full_catalog_content
from modules import db

# ==============================================================================
# MAIN PAGE RENDERING
# ==============================================================================

def render_page() -> None:
    # 1. Initialize System
    initialize_session_state()
    # FORCE: Ensure critical state exists even if init logic was cached/skipped
    # Check if empty BEFORE ensuring, so we know if we need to refresh widgets
    was_empty = not st.session_state.get("inv_no")
    
    from modules.invoice_state import ensure_invoice_no_exists
    ensure_invoice_no_exists()
    
    # If it WAS empty, it means we just generated a new one.
    # We must RERUN to force text_input widget to pick up the new value from session state.
    if was_empty and st.session_state.get("inv_no"):
         st.rerun()
    
    inject_styles()
    
    # 2. Redirect Handler (e.g. after Save)
    if st.session_state.get("_redirect_to_history"):
        st.session_state["_redirect_to_history"] = False
        st.session_state["_needs_rerun"] = False
        st.session_state["menu_selection"] = "📜 Invoice History"  # Switch tab
        st.session_state["nav_key"] = st.session_state.get("nav_key", 0) + 1  # Force nav refresh
        st.rerun()
    
    if st.session_state.get("_needs_rerun"):
        st.session_state["_needs_rerun"] = False
        st.rerun()

    # 3. Header
    page_header("🧾 Event Invoice Builder", "Manage sales, split payments, and generate invoices.")

    # 4. Data Loading
    try:
        # Smart Caching: Only invalidates when DB version changes
        pkg_ver = get_package_version_cached()
        packages = load_packages_cached(pkg_ver)
    except Exception as e:
        st.error(f"Connection Error: {e}")
        packages = []

    # 5. Calculations
    subtotal, grand_total = calculate_totals(
        st.session_state["inv_items"],
        safe_float(st.session_state.get("inv_cashback", 0)),
    )

    # 6. Layout: Sidebar vs Main
    sidebar_col, main_col = st.columns([1, 3], gap="large")
    
    # --- LEFT SIDEBAR ---
    with sidebar_col:
        render_sidebar_packages_v2(packages)
    
    # --- RIGHT MAIN AREA ---
    with main_col:
        
        # 0. FULL CATALOG (Top of Main)
        # Controlled by sidebar button
        if st.session_state.get("show_catalog", False):
            with st.container(border=True):
                c_head, c_close = st.columns([0.85, 0.15])
                c_head.subheader("🌐 Full Catalog Selection")
                if c_close.button("✖ Close", use_container_width=True):
                    st.session_state["show_catalog"] = False
                    st.rerun()
                
                render_full_catalog_content(packages)
            st.divider()

        # A. Form
        render_event_metadata()
        st.write("")
        
        # B. Items / POS
        render_pos_section(subtotal, safe_float(st.session_state.get("inv_cashback", 0)), grand_total)
        st.write("")
        
        # C. Payment Schedule
        render_payment_section(grand_total)
        
        # D. Actions (Generate PDF, Save, Download)
        render_action_buttons(subtotal, grand_total)
        render_download_section()
