import json
import streamlit as st
from datetime import datetime
from typing import Optional

from modules import db
from modules.utils import make_safe_filename
from views.styles import page_header, inject_styles
from ui.formatters import rupiah


# Removed cache to ensure updates are reflected immediately
def _get_invoice_pdf(invoice_id: int) -> Optional[bytes]:
    """Get PDF from stored blob, or regenerate if missing (for old invoices)."""
    try:
        detail = db.get_invoice_details(invoice_id)
        if not detail:
            return None
        
        # 1. Try to use stored PDF blob (instant)
        pdf_blob = detail.get("pdf_blob")
        if pdf_blob:
            return bytes(pdf_blob) if not isinstance(pdf_blob, bytes) else pdf_blob
        
        # 2. Fallback: Regenerate from JSON (for old invoices without blob)
        payload = json.loads(detail["invoice_data"])
        meta = payload.get("meta", {})
        items = payload.get("items", [])
        grand_total = payload.get("grand_total", 0)
        
        from modules import invoice as invoice_mod
        pdf_bytes = invoice_mod.generate_pdf_bytes(meta, items, grand_total)
        
        if hasattr(pdf_bytes, 'read'):
            pdf_bytes.seek(0)
            return pdf_bytes.read()
        return pdf_bytes
    except Exception:
        return None

@st.dialog("⚠️ Confirm Deletion")
def _handle_delete_dialog(invoice_id: int, invoice_no: str):
    st.warning(f"Are you sure you want to delete **{invoice_no}**?")
    st.write("This action cannot be undone.")
    
    col_can, col_del = st.columns(2)
    if col_can.button("Cancel", key=f"d_can_{invoice_id}", use_container_width=True):
        st.rerun()
        
    if col_del.button("Yes, Delete", key=f"d_yes_{invoice_id}", type="primary", use_container_width=True):
        db.delete_invoice(invoice_id)
        st.toast("Invoice deleted.", icon="🗑️")
        st.rerun()

@st.dialog("📤 Kirim via WhatsApp")
def open_wa_dialog(wa_url: str):
    st.warning("⚠️ **PENTING**: File PDF **TIDAK** otomatis terkirim.")
    st.write("Silakan klik tombol di bawah untuk membuka chat, lalu **lampirkan file PDF** yang sudah Anda download secara manual.")
    st.write("")
    st.link_button("🚀 Lanjut ke WhatsApp", wa_url, use_container_width=True)


def render_page():
    inject_styles()
    page_header("📜 Invoice History", "View and manage your saved invoices.")

    # --- Filters Row ---
    f1, f2, f3 = st.columns([2, 1, 1])
    with f1:
        search_q = st.text_input("� Search", placeholder="Invoice no or client name...", label_visibility="collapsed")
    with f2:
        limit = st.selectbox("Show", [10, 25, 50], index=0, label_visibility="collapsed")
    with f3:
        st.write("")  # Spacer

    # --- Load Data ---
    if search_q:
        invoices = db.search_invoices(search_q, limit=limit)
    else:
        invoices = db.get_invoices(limit=limit)
    
    if not invoices:
        st.info("📭 No invoices found. Start by creating your first invoice!")
        return

    # --- Stats Calculation ---
    total_revenue = 0
    cnt_lunas = 0
    cnt_dp = 0
    cnt_unpaid = 0

    for inv in invoices:
        total_revenue += inv.get("total_amount", 0)
        
        # Determine Status for Counting
        p_terms = inv.get("payment_terms")
        if isinstance(p_terms, str):
            try:
                p_terms = json.loads(p_terms)
            except:
                p_terms = []
        
        is_lunas = False
        is_dp = False
        
        if p_terms and isinstance(p_terms, list):
            pelunasan = next((t for t in p_terms if t.get("id") == "full"), None)
            is_lunas = pelunasan and int(float(pelunasan.get("amount", 0))) > 0
            
            if not is_lunas:
                # If not lunas, check if any partial payment (DP) exists
                is_dp = any(int(float(t.get("amount", 0))) > 0 for t in p_terms if t.get("id") != "full")
        
        if is_lunas:
            cnt_lunas += 1
        elif is_dp:
            cnt_dp += 1
        else:
            cnt_unpaid += 1

    # --- Stats Bar ---
    st.markdown(
        f'<div style="display:flex; flex-wrap:wrap; gap:24px; padding:12px 16px; background:#f8fafc; border-radius:8px; margin:16px 0; align-items: center;">'
        f'    <div style="min-width: 100px;">'
        f'        <div style="font-size:0.75rem; color:#64748b; text-transform:uppercase; font-weight:600;">Total Invoices</div>'
        f'        <div style="font-size:1.25rem; font-weight:800; color:#0f172a;">{len(invoices)}</div>'
        f'    </div>'
        f'    <div style="min-width: 140px;">'
        f'        <div style="font-size:0.75rem; color:#64748b; text-transform:uppercase; font-weight:600;">Revenue (Shown)</div>'
        f'        <div style="font-size:1.25rem; font-weight:800; color:#16a34a;">{rupiah(total_revenue)}</div>'
        f'    </div>'
        f'    <div style="width: 1px; height: 32px; background: #e2e8f0;"></div>'
        f'    <div style="display:flex; gap:16px;">'
        f'        <div style="text-align:center;">'
        f'            <div style="font-size:0.75rem; color:#15803d; font-weight:700;">LUNAS</div>'
        f'            <div style="font-size:1.1rem; font-weight:800; color:#166534;">{cnt_lunas}</div>'
        f'        </div>'
        f'        <div style="text-align:center;">'
        f'            <div style="font-size:0.75rem; color:#0369a1; font-weight:700;">DP / CICIL</div>'
        f'            <div style="font-size:1.1rem; font-weight:800; color:#075985;">{cnt_dp}</div>'
        f'        </div>'
        f'        <div style="text-align:center;">'
        f'            <div style="font-size:0.75rem; color:#64748b; font-weight:700;">UNPAID</div>'
        f'            <div style="font-size:1.1rem; font-weight:800; color:#475569;">{cnt_unpaid}</div>'
        f'        </div>'
        f'    </div>'
        f'</div>',
        unsafe_allow_html=True
    )

    # --- Invoice Table ---
    st.markdown(
        """
        <div style="display:grid; grid-template-columns: 1.8fr 1.8fr 1.0fr 1.2fr 1.2fr 0.6fr; gap:8px; padding:10px 12px; 
                    background:#f1f5f9; border-radius:6px; font-size:0.72rem; font-weight:700; 
                    color:#64748b; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:8px;">
            <div>Invoice No</div>
            <div>Client</div>
            <div style="text-align:center;">Status</div>
            <div>Event Date</div>
            <div style="text-align:right;">Amount</div>
            <div style="text-align:center;">Action</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    for inv in invoices:
        inv_id = inv["id"]
        inv_no = inv.get("invoice_no", "UNKNOWN")
        client = inv.get("client_name", "Unknown")
        created_str = inv.get("date", "-")
        wedding_str = inv.get("wedding_date") or "-"
        total = inv.get("total_amount", 0)
        has_proof = inv.get("data_size", 0) > 15000

        # Determine Status
        status_badges = []
        payment_terms = inv.get("payment_terms")
        
        # Parse if string
        if isinstance(payment_terms, str):
            try:
                payment_terms = json.loads(payment_terms)
            except:
                payment_terms = []
        
        status_html = "-"
        if payment_terms and isinstance(payment_terms, list):
            pelunasan = next((t for t in payment_terms if t.get("id") == "full"), None)
            has_full = pelunasan and int(float(pelunasan.get("amount", 0))) > 0
            
            # Count how many other terms (DP, Term 1, etc.) are paid
            paid_others = [t for t in payment_terms if t.get("id") != "full" and int(float(t.get("amount", 0))) > 0]
            dp_count = len(paid_others)
            
            if has_full:
                status_html = "<div style='text-align:center;'><span style='background:#dcfce7; color:#166534; padding:2px 8px; border-radius:12px; font-size:0.65rem; font-weight:700;'>LUNAS</span></div>"
            elif dp_count > 1:
                # Multiple partial payments (e.g. DP + Term 1)
                status_html = "<div style='text-align:center;'><span style='background:#ffedd5; color:#9a3412; padding:2px 8px; border-radius:12px; font-size:0.65rem; font-weight:700;'>DP + TERMIN</span></div>"
            elif dp_count == 1:
                # Just DP (or just one term)
                status_html = "<div style='text-align:center;'><span style='background:#e0f2fe; color:#075985; padding:2px 8px; border-radius:12px; font-size:0.65rem; font-weight:700;'>DP</span></div>"
            else:
                status_html = "<div style='text-align:center;'><span style='background:#f1f5f9; color:#64748b; padding:2px 8px; border-radius:12px; font-size:0.65rem; font-weight:700;'>UNPAID</span></div>"
        else:
             status_html = "<div style='text-align:center;'><span style='background:#f1f5f9; color:#94a3b8; padding:2px 8px; border-radius:12px; font-size:0.65rem; font-weight:700;'>UNKNOWN</span></div>"

        # Row container
        with st.container():
            c1, c2, c3, c4, c5, c6 = st.columns([1.8, 1.8, 1.0, 1.2, 1.2, 0.6], vertical_alignment="center")
            
            with c1:
                proof_icon = " 📎" if has_proof else ""
                st.markdown(f"<div style='font-weight:700; color:#0f172a;'>{inv_no}{proof_icon}</div>", unsafe_allow_html=True)
            
            with c2:
                st.markdown(f"<div style='color:#475569;'>{client}</div>", unsafe_allow_html=True)
            
            with c3:
                st.markdown(status_html, unsafe_allow_html=True)

            with c4:
                st.markdown(f"<div style='color:#64748b;'>{wedding_str}</div>", unsafe_allow_html=True)
            
            with c5:
                st.markdown(f"<div style='text-align:right; font-weight:700; color:#0f172a;'>{rupiah(total)}</div>", unsafe_allow_html=True)
            
            with c6:
                # Optimized: Use Popover to prevent vertical stacking on mobile
                with st.popover("⚙️", use_container_width=True):
                    # Edit
                    if st.button("✏️ Edit Invoice", key=f"ed_{inv_id}", use_container_width=True):
                        _handle_edit(inv_id)
                    
                    # PDF
                    if st.button("📄 Generate PDF", key=f"gen_{inv_id}", use_container_width=True):
                        _handle_reprint(inv_id)
                        
                    # WhatsApp Share
                    phone_raw = inv.get("client_phone")
                    if phone_raw:
                        # Sanitize
                        import re
                        safe_phone = re.sub(r"[^0-9]", "", str(phone_raw))
                        if safe_phone.startswith("0"): safe_phone = "62" + safe_phone[1:]
                        
                        # Get Template
                        default_tpl = """Halo Kak {nama}!

Terima kasih sudah mempercayakan momen spesial Anda kepada kami.

Berikut detail invoice Anda:
Invoice: {inv_no}

Silakan cek file invoice yang sudah kami kirimkan ya. Jika ada pertanyaan, jangan ragu untuk menghubungi kami.

Warm regards,
ORBIT Team"""
                        tpl = db.get_config("wa_template_default") or default_tpl
                        msg = tpl.replace("{nama}", client).replace("{inv_no}", inv_no)
                        
                        import urllib.parse
                        encoded_msg = urllib.parse.quote(msg)
                        
                        if safe_phone:
                            wa_url = f"https://wa.me/{safe_phone}?text={encoded_msg}"
                        else:
                            wa_url = f"https://api.whatsapp.com/send?text={encoded_msg}"
                            
                    if st.button("🗑️ Delete", key=f"del_{inv_id}", type="primary", use_container_width=True):
                         _handle_delete_dialog(inv_id, inv_no)

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
        st.session_state["inv_client_phone"] = meta.get("client_phone", "")  # Backward compatible
        st.session_state["inv_client_email"] = meta.get("client_email", "")
        st.session_state["inv_venue"] = meta.get("venue", "")
        
        # Handle date parsing (try multiple formats with locale enforcement)
        try:
            w_date_str = meta.get("wedding_date", "")
            if w_date_str:
                import locale
                # Save current locale and set to C/English for parsing
                try:
                    saved_locale = locale.getlocale(locale.LC_TIME)
                    locale.setlocale(locale.LC_TIME, 'C')
                except:
                    saved_locale = None
                
                parsed = None
                # Try formats in order
                for fmt in ["%A, %d %B %Y", "%d %B %Y", "%Y-%m-%d"]:
                    try:
                        parsed = datetime.strptime(w_date_str, fmt).date()
                        break
                    except ValueError:
                        continue
                
                # Restore locale
                if saved_locale:
                    try:
                        locale.setlocale(locale.LC_TIME, saved_locale)
                    except:
                        pass
                
                if parsed:
                    st.session_state["inv_wedding_date"] = parsed
        except Exception as e:
            print(f"[DEBUG] Date parse error: {e}")
            
        st.session_state["inv_cashback"] = float(meta.get("cashback", 0))
        
        # Restore payment terms - backward compatible
        payment_terms = meta.get("payment_terms")
        if payment_terms:
            st.session_state["payment_terms"] = payment_terms
        else:
            # Convert old format to new
            st.session_state["payment_terms"] = [
                {"id": "dp", "label": "Down Payment", "amount": int(meta.get("pay_dp1", 0)), "locked": True},
                {"id": "t2", "label": "Payment 2", "amount": int(meta.get("pay_term2", 0)), "locked": False},
                {"id": "t3", "label": "Payment 3", "amount": int(meta.get("pay_term3", 0)), "locked": False},
                {"id": "full", "label": "Pelunasan", "amount": int(meta.get("pay_full", 0)), "locked": True},
            ]
            # Remove zero-amount middle terms for cleaner UI
            st.session_state["payment_terms"] = [
                t for t in st.session_state["payment_terms"] 
                if t.get("locked") or t.get("amount", 0) > 0
            ]
        
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


@st.dialog("📄 Invoice Options")
def _handle_reprint(invoice_id: int):
    """Shows PDF options using stored blob or regenerating if needed."""
    # 1. Fetch Data
    detail = db.get_invoice_details(invoice_id)
    if not detail:
        st.error("Invoice not found.")
        return
    
    # Parse metadata for display
    try:
        payload = json.loads(detail["invoice_data"])
        meta = payload.get("meta", {})
    except:
        meta = {}

    # 2. Get PDF (from blob or regenerate)
    pdf_bytes = None
    pdf_blob = detail.get("pdf_blob")
    
    if pdf_blob:
        # Instant: Use stored PDF
        pdf_bytes = bytes(pdf_blob) if not isinstance(pdf_blob, bytes) else pdf_blob
    else:
        # Fallback: Regenerate for old invoices
        with st.spinner("Generating PDF..."):
            try:
                items = payload.get("items", [])
                grand_total = payload.get("grand_total", 0)
                
                from modules import invoice as invoice_mod
                pdf_bytes = invoice_mod.generate_pdf_bytes(meta, items, grand_total)
                
                if hasattr(pdf_bytes, 'read'):
                    pdf_bytes.seek(0)
                    pdf_bytes = pdf_bytes.read()
            except Exception as e:
                st.error(f"Generation failed: {e}")
                return

    # 3. Actions UI
    if pdf_bytes:
        inv_no_safe = make_safe_filename(meta.get("inv_no", "invoice"))
        
        st.success("✅ PDF Ready!")
        st.write("")
        
        col_dl, col_wa = st.columns(2)
        
        with col_dl:
            st.download_button(
                label="📥 Download PDF",
                data=pdf_bytes,
                file_name=f"{inv_no_safe}.pdf",
                mime="application/pdf",
                key=f"dl_modal_{invoice_id}",
                type="primary",
                use_container_width=True
            )
            
        with col_wa:
            # WhatsApp Logic in Dialog
            phone_raw = meta.get("client_phone") or detail.get("client_phone")
            
            if phone_raw:
                import re
                import urllib.parse
                
                # Sanitize
                safe_phone = re.sub(r"[^0-9]", "", str(phone_raw))
                if safe_phone.startswith("0"): safe_phone = "62" + safe_phone[1:]
                
                # Template
                default_tpl = """Halo Kak {nama}!

Terima kasih sudah mempercayakan momen spesial Anda kepada kami.

Berikut detail invoice Anda:
Invoice: {inv_no}

Silakan cek file invoice yang sudah kami kirimkan ya. Jika ada pertanyaan, jangan ragu untuk menghubungi kami.

Warm regards,
ORBIT Team"""
                tpl = db.get_config("wa_template_default") or default_tpl
                msg = tpl.replace("{nama}", meta.get("client_name", "Kak")).replace("{inv_no}", meta.get("inv_no", "-"))
                
                encoded_msg = urllib.parse.quote(msg)
                
                if safe_phone:
                    wa_url = f"https://wa.me/{safe_phone}?text={encoded_msg}"
                else:
                    wa_url = f"https://api.whatsapp.com/send?text={encoded_msg}"
                    
                if st.button("📱 WhatsApp", key=f"wa_modal_{invoice_id}", use_container_width=True):
                    open_wa_dialog(wa_url)
            else:
                st.button("📱 WhatsApp (No Number)", key=f"wa_modal_dis_{invoice_id}", disabled=True, use_container_width=True)
        
        st.write("")
        st.caption("Press Esc to close.")
