import json
import streamlit as st
from datetime import datetime

from modules import db, invoice as invoice_mod
from ui.components import page_header
from ui.formatters import rupiah
from views.styles import inject_styles


def render_page():
    inject_styles()
    page_header("📜 Invoice History", "View and manage your saved invoices.")

    # --- Filters Row ---
    f1, f2, f3 = st.columns([2, 1, 1])
    with f1:
        search_q = st.text_input("� Search", placeholder="Invoice no or client name...", label_visibility="collapsed")
    with f2:
        limit = st.selectbox("Show", [25, 50, 100], index=0, label_visibility="collapsed")
    with f3:
        st.write("")  # Spacer

    # --- Load Data ---
    raw_invoices = db.get_invoices(limit=limit)
    
    if not raw_invoices:
        st.info("📭 No invoices found. Start by creating your first invoice!")
        return

    # Filter
    if search_q:
        q = search_q.lower()
        invoices = [inv for inv in raw_invoices 
                    if q in str(inv.get("invoice_no", "")).lower() 
                    or q in str(inv.get("client_name", "")).lower()]
    else:
        invoices = raw_invoices

    # --- Stats Bar ---
    total_revenue = sum(inv.get("total_amount", 0) for inv in invoices)
    st.markdown(
        f"""
        <div style="display:flex; gap:24px; padding:12px 16px; background:#f8fafc; border-radius:8px; margin:16px 0;">
            <div>
                <div style="font-size:0.75rem; color:#64748b; text-transform:uppercase; font-weight:600;">Total Invoices</div>
                <div style="font-size:1.25rem; font-weight:800; color:#0f172a;">{len(invoices)}</div>
            </div>
            <div>
                <div style="font-size:0.75rem; color:#64748b; text-transform:uppercase; font-weight:600;">Total Revenue</div>
                <div style="font-size:1.25rem; font-weight:800; color:#16a34a;">{rupiah(total_revenue)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # --- Invoice Table ---
    st.markdown(
        """
        <div style="display:grid; grid-template-columns: 2fr 2fr 1.5fr 1fr 1.2fr; gap:8px; padding:10px 12px; 
                    background:#f1f5f9; border-radius:6px; font-size:0.72rem; font-weight:700; 
                    color:#64748b; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:8px;">
            <div>Invoice No</div>
            <div>Client</div>
            <div>Date</div>
            <div style="text-align:right;">Amount</div>
            <div style="text-align:center;">Actions</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    for inv in invoices:
        inv_id = inv["id"]
        inv_no = inv.get("invoice_no", "UNKNOWN")
        client = inv.get("client_name", "Unknown")
        date_str = inv.get("date", "-")
        total = inv.get("total_amount", 0)
        has_proof = inv.get("data_size", 0) > 15000

        # Row container
        with st.container():
            c1, c2, c3, c4, c5 = st.columns([2, 2, 1.5, 1, 1.2], vertical_alignment="center")
            
            with c1:
                proof_icon = " 📎" if has_proof else ""
                st.markdown(f"<div style='font-weight:700; color:#0f172a;'>{inv_no}{proof_icon}</div>", unsafe_allow_html=True)
            
            with c2:
                st.markdown(f"<div style='color:#475569;'>{client}</div>", unsafe_allow_html=True)
            
            with c3:
                st.markdown(f"<div style='color:#64748b; font-size:0.85rem;'>{date_str}</div>", unsafe_allow_html=True)
            
            with c4:
                st.markdown(f"<div style='text-align:right; font-weight:700; color:#0f172a;'>{rupiah(total)}</div>", unsafe_allow_html=True)
            
            with c5:
                btn1, btn2, btn3 = st.columns(3)
                with btn1:
                    if st.button("✏️", key=f"ed_{inv_id}", help="Edit"):
                        _handle_edit(inv_id)
                with btn2:
                    if st.button("📄", key=f"pr_{inv_id}", help="Reprint PDF"):
                        _handle_reprint(inv_id)
                with btn3:
                    if st.button("🗑️", key=f"del_{inv_id}", help="Delete"):
                        st.session_state[f"confirm_del_{inv_id}"] = True

            # Delete confirmation
            if st.session_state.get(f"confirm_del_{inv_id}"):
                with st.container():
                    st.warning(f"Delete {inv_no}?")
                    dc1, dc2 = st.columns(2)
                    if dc1.button("Cancel", key=f"cancel_{inv_id}"):
                        st.session_state[f"confirm_del_{inv_id}"] = False
                        st.rerun()
                    if dc2.button("Yes, Delete", key=f"confirm_{inv_id}", type="primary"):
                        db.delete_invoice(inv_id)
                        st.session_state[f"confirm_del_{inv_id}"] = False
                        st.toast("Invoice deleted.", icon="🗑️")
                        st.rerun()

            st.markdown("<hr style='margin:4px 0; border:none; border-top:1px solid #e2e8f0;'>", unsafe_allow_html=True)


def _handle_edit(invoice_id: int):
    """Restores state from invoice data and redirects to Editor."""
    detail = db.get_invoice_details(invoice_id)
    if not detail:
        st.error("Invoice data not found.")
        return

    try:
        payload = json.loads(detail["invoice_data"])
        meta = payload.get("meta", {})
        
        # Restore State
        st.session_state["inv_items"] = payload.get("items", [])
        st.session_state["inv_no"] = meta.get("inv_no", "")
        st.session_state["inv_title"] = meta.get("title", "")
        st.session_state["inv_client_name"] = meta.get("client_name", "")
        st.session_state["inv_client_email"] = meta.get("client_email", "")
        st.session_state["inv_venue"] = meta.get("venue", "")
        
        # Handle date parsing
        try:
            w_date_str = meta.get("wedding_date", "")
            if w_date_str:
                st.session_state["inv_wedding_date"] = datetime.strptime(w_date_str, "%d %B %Y").date()
        except:
            pass
            
        st.session_state["inv_cashback"] = float(meta.get("cashback", 0))
        st.session_state["pay_dp1"] = int(meta.get("pay_dp1", 0))
        st.session_state["pay_term2"] = int(meta.get("pay_term2", 0))
        st.session_state["pay_term3"] = int(meta.get("pay_term3", 0))
        st.session_state["pay_full"] = int(meta.get("pay_full", 0))
        
        st.session_state["inv_terms"] = meta.get("terms", "")
        st.session_state["bank_nm"] = meta.get("bank_name", "")
        st.session_state["bank_ac"] = meta.get("bank_acc", "")
        st.session_state["bank_an"] = meta.get("bank_holder", "")
        
        # Payment Proof (Normalize to List)
        pp_data = meta.get("payment_proof")
        if pp_data and not isinstance(pp_data, list):
            pp_data = [pp_data]
        st.session_state["pp_cached"] = pp_data
        
        # Track editing
        st.session_state["editing_invoice_id"] = invoice_id
        
        # Redirect
        st.session_state["menu_selection"] = "🧾 Create Invoice"
        st.session_state["nav_key"] = st.session_state.get("nav_key", 0) + 1

        st.toast("Invoice loaded for editing!", icon="✏️")
        st.rerun()
        
    except Exception as e:
        st.error(f"Failed to load: {e}")


def _handle_reprint(invoice_id: int):
    """Regenerates PDF and shows download button."""
    detail = db.get_invoice_details(invoice_id)
    if not detail:
        st.error("Invoice not found.")
        return

    try:
        payload = json.loads(detail["invoice_data"])
        meta = payload.get("meta", {})
        items = payload.get("items", [])
        grand_total = payload.get("grand_total", 0)
        
        pdf_bytes = invoice_mod.generate_pdf_bytes(meta, items, grand_total)
        
        if pdf_bytes:
            inv_no = meta.get("inv_no", "invoice").replace("/", "_")
            st.download_button(
                label=f"📥 Download {inv_no}.pdf",
                data=pdf_bytes,
                file_name=f"{inv_no}.pdf",
                mime="application/pdf",
                key=f"dl_{invoice_id}"
            )
            
    except Exception as e:
        st.error(f"PDF generation failed: {e}")
