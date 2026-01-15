import streamlit as st
from datetime import datetime
from modules.utils import safe_float, calculate_totals
from modules.invoice_state import initialize_session_state, load_packages_cached
from views.styles import inject_styles, page_header
from views.invoice_components import (
    render_event_metadata,
    render_pos_section,
    render_payment_section,
    render_action_buttons,
    render_download_section
)
from views.sidebar_components import render_sidebar_packages_v2

# ==============================================================================
# MAIN PAGE RENDERING
# ==============================================================================

def render_page() -> None:
    # 1. Initialize System
    initialize_session_state()
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
        packages = load_packages_cached()
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
