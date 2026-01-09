import json
import base64
import streamlit as st
from datetime import datetime

from modules import db, invoice as invoice_mod
from ui.components import page_header, section, danger_container
from ui.formatters import rupiah

def render_page():
    page_header("📜 Invoice History", "View past invoices and reprint PDFs.")
    
    # --- ISO-STYLE CUSTOM CSS ---
    st.markdown("""
    <style>
    .iso-card {
        background-color: white;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        transition: box-shadow 0.2s;
    }
    .iso-card:hover {
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-color: #d1d5db;
    }
    .iso-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .iso-meta {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        color: #6b7280;
        font-size: 0.85rem;
    }
    .iso-badg {
         display: inline-flex;
         align-items: center;
         padding: 2px 8px;
         border-radius: 999px;
         font-size: 0.7rem;
         font-weight: 600;
         text-transform: uppercase;
         letter-spacing: 0.05em;
    }
    .badg-green { background: #dcfce7; color: #166534; }
    .badg-orange { background: #ffedd5; color: #9a3412; }
    .badg-red { background: #fee2e2; color: #991b1b; }
    </style>
    """, unsafe_allow_html=True)

    # --- Search & Filter ---
    col1, col2 = st.columns([2, 1])
    search_q = col1.text_input("🔎 Search (Invoice No / Client)", placeholder="e.g. INV/01 or John Doe")
    limit = col2.selectbox("Show Last", [20, 50, 100], index=1)

    st.write("")

    # --- Load Data ---
    raw_invoices = db.get_invoices(limit=limit)
    
    if not raw_invoices:
        st.info("No invoice history found.")
        return

    # Filter in memory (simple) if search_q exists
    if search_q:
        q = search_q.lower()
        filtered = []
        for inv in raw_invoices:
            no = str(inv.get("invoice_no", "")).lower()
            cl = str(inv.get("client_name", "")).lower()
            if q in no or q in cl:
                filtered.append(inv)
        invoices = filtered
    else:
        invoices = raw_invoices

    st.caption(f"Showing **{len(invoices)}** records.")

    # --- Render List (ISO Card Style) ---
    for inv in invoices:
        inv_id = inv["id"]
        inv_no = inv.get("invoice_no", "UNKNOWN")
        client = inv.get("client_name", "Unknown Client")
        date_str = inv.get("date", "-")
        total = inv.get("total_amount", 0)
        
        # Attachment Icon
        has_proof = inv.get("data_size", 0) > 15000
        icon_html = "<span style='margin-left:6px; font-size:14px; color:#3b82f6;'>📎 Proof Attached</span>" if has_proof else ""

        with st.container():
            st.markdown(f"""
            <div class="iso-card">
                <div class="iso-row">
                    <div>
                        <div style="font-weight:700; font-size:1.1rem; color:#111827;">
                            {inv_no} {icon_html}
                        </div>
                        <div class="iso-meta" style="margin-top:4px;">
                            {client} • {date_str}
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-weight:800; font-size:1.1rem; color:#111827;">{rupiah(total)}</div>
                        <div style="margin-top:4px;">
                             <span class="iso-badg badg-green">RECORDED</span>
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Actions Row (Compact)
            c1, c2, c3 = st.columns([1, 1, 4])
            with c1:
                 if st.button("✏️ Edit", key=f"ed_{inv_id}", use_container_width=True):
                     _handle_edit(inv_id)
            with c2:
                 if st.button("🖨️ PDF", key=f"pr_{inv_id}", use_container_width=True):
                     _handle_reprint(inv_id)
            with st.expander("🗑️ Delete", expanded=False):
                 st.caption(f"Delete {inv_no}?")
                 if st.button("Confirm Delete", key=f"del_{inv_id}", type="primary"):
                     db.delete_invoice(inv_id)
                     st.rerun()

    st.write("")

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
        # Restore Title & Dates
        st.session_state["inv_title"] = meta.get("title", "")
        st.session_state["inv_client_name"] = meta.get("client_name", "")
        st.session_state["inv_client_email"] = meta.get("client_email", "")
        st.session_state["inv_venue"] = meta.get("venue", "")
        
        # Handle date parsing safely
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
        
        # Restore Proof Cache
        proof = meta.get("payment_proof", "")
        if proof:
            st.session_state["pp_cached"] = proof
        
        # Track that we are editing this ID
        st.session_state["editing_invoice_id"] = invoice_id
        
        # Redirect
        target_nav = "🧾 Create Invoice"
        st.session_state["menu_selection"] = target_nav
        
        # Force widget reset via key change
        st.session_state["nav_key"] = st.session_state.get("nav_key", 0) + 1

        st.toast("Invoice loaded for editing!", icon="✏️")
        st.rerun()
        
    except Exception as e:
        st.error(f"Failed to load invoice: {e}")

def _handle_reprint(invoice_id: int):
    # ... existing reprint logic ...
    """
    Loads full invoice data, regenerates PDF, and shows download button.
    """
    detail = db.get_invoice_details(invoice_id)
    if not detail:
        st.error("Invoice data not found.")
        return

    try:
        # Parse JSON payload
        payload = json.loads(detail["invoice_data"])
        
        meta = payload.get("meta", {})
        items = payload.get("items", [])
        grand_total = payload.get("grand_total", 0)
        
        # Regenerate PDF
        pdf_bytes = invoice_mod.generate_pdf_bytes(meta, items, grand_total)
        
        if pdf_bytes:
            st.toast("PDF Regenerated!", icon="✅")
            
            # Show download button in a dialog or just below
            inv_no = meta.get("inv_no", "invoice").replace("/", "_")
            st.download_button(
                label=f"📥 Download PDF ({inv_no})",
                data=pdf_bytes,
                file_name=f"{inv_no}.pdf",
                mime="application/pdf",
                key=f"dl_{invoice_id}"
            )
            
    except Exception as e:
        st.error(f"Failed to regenerate PDF: {e}")
