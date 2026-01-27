import streamlit as st
from datetime import datetime
from typing import List, Dict, Any, Tuple
from modules import db
from modules.utils import (
    sanitize_text, 
    rupiah, 
    safe_int, 
    safe_float, 
    make_safe_filename,
    desc_to_lines, 
    normalize_desc_text
)
from modules.invoice_state import (
    invalidate_pdf, 
    DEFAULT_FOOTER_ITEMS,
    CATALOG_CACHE_TTL_SEC
)
from views.styles import (
    section, 
    danger_container, 
    render_package_card, 
    POS_COLUMN_RATIOS
)
from controllers.invoice_callbacks import (
    cb_update_invoice_no,
    cb_add_item_to_cart,
    cb_update_item_qty,
    cb_delete_item,
    cb_update_bundle_price,
    cb_fill_remaining_payment,
    cb_merge_selected_from_ui,
    cb_unmerge_bundle,
    _cart_bundle_items,
    _cart_non_bundle_items,
    action_generate_pdf,
    handle_save_history,
    cb_reset_transaction,
    cb_save_defaults,
    cb_client_name_changed
)
# --- Constants & Helpers ---
PAYMENT_STEP = 1_000_000
try:
    from views.packages_view import CATEGORIES
except ImportError:
    CATEGORIES = ["Utama", "Bonus"]
def payment_integrity_status(
    grand_total: float,
    dp1: int,
    term2: int,
    term3: int,
    full: int,
) -> Tuple[str, str, int]:
    total_scheduled = int(dp1) + int(term2) + int(term3) + int(full)
    balance = int(grand_total) - total_scheduled
    if grand_total <= 0:
        return "INFO", "Add items to cart to calculate payments.", balance
    if balance == 0:
        return "BALANCED", "Schedule matches Grand Total.", balance
    if balance > 0:
        return "UNALLOCATED", f"{rupiah(balance)} remaining.", balance
    return "OVER", f"{rupiah(abs(balance))} excess.", balance
# --- Components ---
# Sidebar logic moved to views/sidebar_components.py
def render_event_metadata() -> None:
    # --- Section: Event & Client ---
    st.markdown('<div class="sidebar-header"><h3>📝 Event Details</h3></div>', unsafe_allow_html=True)
    # Spacer removed based on user feedback (too much empty space)
    
    # Use a container for better grouping
    # Use a container for better grouping
    with st.container():
        # Row 1: Core Event Data
        c1, c2, c3 = st.columns(3)
        with c1:
            st.text_input("Invoice No", key="inv_no", placeholder="e.g. INV/2026/001", on_change=invalidate_pdf, help="To change the starting sequence (e.g. to 250), go to System Tools in the Sidebar.")
        with c2:
            st.date_input("Wedding Date", key="inv_wedding_date", on_change=invalidate_pdf)
        with c3:
            st.text_input("Venue", key="inv_venue", placeholder="e.g. Grand Ballroom Hotel Mulia", on_change=invalidate_pdf)
        # Row 2: Client & Context
        c4, c5, c6 = st.columns(3)
        with c4:
             st.text_input("Client Name", key="inv_client_name", placeholder="e.g. Romeo & Juliet", on_change=cb_client_name_changed)
        with c5:
            # WhatsApp with number-only validation
            def sanitize_phone():
                import re
                current = st.session_state.get("inv_client_phone", "")
                cleaned = re.sub(r"[^0-9]", "", current)
                if cleaned != current:
                    st.session_state["inv_client_phone"] = cleaned
                invalidate_pdf()
            
            st.text_input("Client WhatsApp", key="inv_client_phone", placeholder="e.g. 08123456789", on_change=sanitize_phone)
        with c6:
             st.text_input("Event / Title", key="inv_title", placeholder="e.g. Wedding Reception 2026", on_change=invalidate_pdf)
    
    st.markdown("<div style='margin-bottom:24px;'></div>", unsafe_allow_html=True)
    # Banking & WhatsApp Config (Collapsible)
    # Trick: Use a dynamic key to force reset (collapse) after save
    if "_config_exp_key" not in st.session_state:
        st.session_state["_config_exp_key"] = 0
        
    with st.expander("🏦 Bank, Terms, WhatsApp & Footer", expanded=False):
        tab_bank, tab_terms, tab_wa, tab_footer = st.tabs(["🏦 Bank Data", "📜 Terms", "📱 WhatsApp", "📝 Footer"])
        
        with tab_bank:
            b_col1, b_col2, b_col3 = st.columns(3)
            b_col1.text_input("Bank Name", key="bank_nm", on_change=invalidate_pdf)
            b_col2.text_input("Account No", key="bank_ac", on_change=invalidate_pdf)
            b_col3.text_input("Account Holder", key="bank_an", on_change=invalidate_pdf)
        with tab_terms:
            st.text_area("Terms & Conditions", key="inv_terms", height=120, on_change=invalidate_pdf)
            
        with tab_wa:
            st.caption("Template Placeholder: `{nama}`, `{inv_no}`")
            # Plain text template relative to user request to avoid encoding issues
            default_wa_template = "Halo Kak {nama}!\n\nTerima kasih sudah mempercayakan momen spesial Anda kepada kami.\n\nBerikut detail invoice Anda:\nInvoice {inv_no}\n\nSilakan cek file invoice yang sudah kami kirimkan ya. Jika ada pertanyaan, jangan ragu untuk menghubungi kami.\n\nWarm regards,\nORBIT Team"
            
            if "wa_template" not in st.session_state:
                st.session_state["wa_template"] = db.get_config("wa_template_default") or default_wa_template
            
            st.text_area("WhatsApp Template", key="wa_template", height=200, label_visibility="collapsed")
            
        with tab_footer:
            st.caption("Contact Info (Satu baris per item)")
            if "inv_footer" not in st.session_state:
                 st.session_state["inv_footer"] = db.get_config("inv_footer_default", DEFAULT_FOOTER_ITEMS)
            # Auto-repair corrupted text (e.g. replacement characters)
            if "\ufffd" in st.session_state.get("inv_footer", ""):
                st.session_state["inv_footer"] = DEFAULT_FOOTER_ITEMS
            st.text_area("Footer Text", key="inv_footer", height=120, on_change=invalidate_pdf, label_visibility="collapsed")
            
        st.write("")
        if st.button("💾 Save as Default", help="Save these settings as new system defaults"):
            cb_save_defaults()
def render_pos_section(subtotal: float, cashback: float, grand_total: float) -> None:
    # --- Section: Bill Items ---
    st.markdown('<div class="sidebar-header"><h3>🛒 Bill Items</h3></div>', unsafe_allow_html=True)
    st.caption("ℹ️ **Tip:** Checklist 2 item atau lebih untuk menggabungkan (**Merge Bundle**).")
    st.write("")
    
    # 1) Headers (Desktop Only)
    # responsive grid matching POS_COLUMN_RATIOS
    # [2.2, 0.8, 0.6, 1.2, 0.5]
    grid_template = "2.2fr 0.8fr 0.6fr 1.2fr 0.5fr" 
    
    st.markdown(
        f"""
        <div class="mobile-hidden" style="
            display: grid; 
            grid-template-columns: {grid_template}; 
            gap: 1rem; 
            margin-bottom: 8px; 
            border-bottom: 1px solid #eee;
            padding-bottom: 8px;
            font-size: 0.8rem;
            color: #6b7280;
        ">
            <div>Description</div>
            <div>Price</div>
            <div>Qty</div>
            <div>Total</div>
            <div>Action</div>
        </div>
        """, 
        unsafe_allow_html=True
    )
    # 2) Items Loop
    items = st.session_state.get("inv_items", [])
    if not items:
        st.info("Basket is empty. Select packages from the sidebar.")
    else:
        for idx, item in enumerate(items):
            item_id = str(item.get("__id"))
            is_bundle = item.get("_bundle", False)
            
            bg_style = "background-color: #fcfcfc;" if is_bundle else ""
            
            c1, c2, c3, c4, c5 = st.columns(POS_COLUMN_RATIOS)
            
            # Col 1: Desc + Checkbox
            with c1:
                col_sel, col_desc = st.columns([0.15, 0.85])
                with col_sel:
                    # Bundling Selection Checkbox
                    is_sel = False
                    if not is_bundle:
                        # Check if this item is in current selection
                        current_sel = st.session_state.get("bundle_sel", [])
                        is_sel = (item_id in current_sel)
                        
                        def _on_check(oid=item_id):
                            csel = st.session_state.get("bundle_sel", [])
                            # Toggle
                            if oid in csel:
                                csel.remove(oid)
                            else:
                                csel.append(oid)
                            st.session_state["bundle_sel"] = csel
                            
                        st.checkbox(
                            "Select", 
                            key=f"sel_{item_id}", 
                            value=is_sel, 
                            label_visibility="collapsed",
                            on_change=_on_check
                        )
                
                with col_desc:
                    icon = "📦" if is_bundle else "🔹"
                    st.markdown(f"**{icon} {item.get('Description', 'Item')}**")
                    
                    # Show details text (limit 2-3 lines)
                    details_text = item.get('Details', '')
                    if details_text:
                        lines = desc_to_lines(normalize_desc_text(details_text))
                        for line in lines[:3]: # Max 3 lines
                             st.markdown(f"<div style='font-size:0.75rem; color:#6b7280; line-height:1.2; margin-left:4px;'>• {line}</div>", unsafe_allow_html=True)
                        if len(lines) > 3:
                             st.markdown(f"<div style='font-size:0.7rem; color:#9ca3af; margin-left:4px; font-style:italic;'>+ {len(lines)-3} items...</div>", unsafe_allow_html=True)
                    if is_bundle:
                        st.caption("Bundled Item")
                        if st.button("Unmerge", key=f"unmerge_{item_id}", help="Revert to original items"):
                            cb_unmerge_bundle(item_id)
                            st.rerun()
            # Col 2: Price (Editable for Bundles)
            with c2:
                if is_bundle:
                    # Bundle price logic...
                    k_bp = f"bundle_price_{item_id}"
                    st.number_input(
                        "Price",
                        value=int(item.get("Price", 0)),
                        step=500_000,
                        key=k_bp,
                        label_visibility="collapsed",
                        on_change=cb_update_bundle_price,
                        args=(item_id, k_bp)
                    )
                else:
                    st.write(rupiah(item.get("Price", 0)))
            
            # Col 3: Qty
            with c3:
                k_qty = f"qty_{item_id}"
                st.number_input(
                    "Qty", 
                    min_value=1, 
                    value=int(item.get("Qty", 1)), 
                    key=k_qty, 
                    label_visibility="collapsed",
                    disabled=is_bundle,  # Bundle qty locked to 1
                    on_change=cb_update_item_qty,
                    args=(item_id, k_qty)
                )
            # Col 4: Total
            with c4:
                st.write(rupiah(item.get("Total", 0)))
            # Col 5: Delete
            with c5:
                st.button(
                    "🗑️", 
                    key=f"del_{item_id}", 
                    on_click=cb_delete_item, 
                    args=(item_id,),
                    type="secondary"
                )
            
            st.markdown("<hr style='margin:4px 0;'>", unsafe_allow_html=True)
            
    # 3) Totals & Bundle Actions
    st.write("")
    bc1, bc2 = st.columns([1, 1])
    
    with bc1:
        # Bundle Logic
        sel_count = len(st.session_state.get("bundle_sel", []))
        if sel_count >= 2:
            st.caption(f"{sel_count} items selected")
            with st.popover("🔗 Merge as Bundle"):
                st.text_input("Bundle Title", key="bundle_title", placeholder="My Custom Package")
                mode = st.radio("Price Mode", ["Sum of selected", "Custom"], key="bundle_price_mode")
                if mode == "Custom":
                    st.number_input("Custom Price", min_value=0, step=500_000, key="bundle_custom_price")
                
                st.button("Confirm Merge", type="primary", on_click=cb_merge_selected_from_ui)
                    
    with bc2:
        # Totals Display
        def _row(lbl, val, bold=False):
            s = "font-weight:700;" if bold else ""
            return f"<div style='display:flex; justify-content:space-between; {s}'><span>{lbl}</span><span>{val}</span></div>"
            
        html_totals = f"""
        <div style="background:#f8f9fa; padding:12px; border-radius:8px;">
            {_row("Subtotal", rupiah(subtotal))}
        </div>
        """
        st.markdown(html_totals, unsafe_allow_html=True)
        
        # Cashback Input
        c_cb = st.number_input(
            "Cashback / Discount", 
            min_value=0, 
            step=500_000, 
            key="inv_cashback", 
            on_change=invalidate_pdf
        )
        if c_cb > 0:
            st.caption("ℹ️ *Menggunakan Template Invoice Diskon*")
        
        html_grand = f"""
        <div style="background:#e3f2fd; padding:12px; border-radius:8px; margin-top:8px; color:#1565c0;">
            {_row("Grand Total", rupiah(grand_total), bold=True)}
        </div>
        """
        st.markdown(html_grand, unsafe_allow_html=True)
        
    st.markdown("</div>", unsafe_allow_html=True) # End Section
def render_payment_section(grand_total: float) -> None:
    # --- Section: Payment (Unified) ---
    st.markdown('<div class="sidebar-header"><h3>💳 Payment Manager</h3></div>', unsafe_allow_html=True)
    st.caption("🔒 **DP** dan **Pelunasan** terkunci. Tambahkan termin pembayaran sesuai kebutuhan.")
    st.write("")
    
    tab_schedule, tab_proof = st.tabs(["💳 Schedule", "📸 Proof"])
    # === TAB 1: SCHEDULE ===
    with tab_schedule:
        st.write("")
        terms = st.session_state.get("payment_terms", [])
        
        # Calculate Integrity
        dp1 = safe_int(st.session_state.get("pay_dp1", terms[0]["amount"] if terms else 0))
        # Sum others dynamically if needed, but here we iterate
        total_alloc = sum([int(t.get("amount", 0)) for t in terms])
        remaining = int(grand_total) - total_alloc
        
        # Status Logic
        if grand_total <= 0:
            status, msg = "INFO", "Add items to cart to calculate payments."
        elif remaining == 0:
            status, msg = "BALANCED", "Payment fully allocated!"
        elif remaining > 0:
            status, msg = "UNALLOCATED", f"Remaining: Rp {remaining:,.0f}".replace(",", ".")
        else:
            status, msg = "OVER", f"Over by: Rp {abs(remaining):,.0f}".replace(",", ".")
        
        badge_cls = {"BALANCED": "badg-green", "UNALLOCATED": "badg-orange", "OVER": "badg-red", "INFO": "badg-blue"}.get(status, "badg-blue")
        # Status Bar
        st.markdown(
            f"""
            <div class="statusbar" style="margin-bottom:16px;">
              <div>
                <div class="status-title">Payment Status</div>
                <div class="muted">{sanitize_text(msg)}</div>
              </div>
              <div class="status-right">
                <span class="iso-badg {badge_cls}">{status}</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # Dynamic Payment Terms UI
        for idx, term in enumerate(terms):
            term_id = term.get("id", f"term_{idx}")
            is_locked = term.get("locked", False)
            label_key = f"pay_label_{term_id}"
            amt_key = f"pay_amt_{term_id}"
            
            col_label, col_amount, col_action = st.columns([2, 2, 0.5])
            
            with col_label:
                k_args = {"value": term.get("label", f"Payment {idx+1}")}
                if label_key in st.session_state:
                     k_args.pop("value", None)
                
                st.text_input(
                    "Label", 
                    key=label_key,
                    label_visibility="collapsed",
                    disabled=is_locked,
                    on_change=invalidate_pdf,
                    **k_args
                )
            
            with col_amount:
                n_args = {"value": term.get("amount", 0)}
                if amt_key in st.session_state:
                     n_args.pop("value", None)
                     
                st.number_input(
                    "Amount",
                    step=PAYMENT_STEP,
                    key=amt_key,
                    label_visibility="collapsed",
                    on_change=invalidate_pdf,
                    **n_args
                )
            
            # Sync widget values back to payment_terms list
            if label_key in st.session_state and not is_locked:
                st.session_state["payment_terms"][idx]["label"] = st.session_state[label_key]
            if amt_key in st.session_state:
                st.session_state["payment_terms"][idx]["amount"] = int(st.session_state[amt_key])
            
            with col_action:
                if is_locked:
                    st.markdown("🔒", help="Required term")
                elif len(terms) > 2:  # Only allow delete if > 2 terms
                    if st.button("🗑️", key=f"del_term_{term_id}", help="Remove term"):
                        st.session_state["payment_terms"].pop(idx)
                        invalidate_pdf()
                        st.rerun()
                else:
                    st.write("")  # Empty placeholder
            
            # Show formatted amount caption (from synced value)
            current_amt = st.session_state.get(amt_key, term.get("amount", 0))
            if current_amt > 0:
                st.caption(f"Rp {int(current_amt):,}".replace(",", "."))
        # Add Term Button (max 6 terms)
        st.write("")
        if len(terms) < 6:
            if st.button("➕ Add Payment Term", use_container_width=True):
                new_id = f"t{len(terms)+1}_{datetime.now().strftime('%H%M%S')}"
                # Insert before Pelunasan (last locked term)
                pelunasan_idx = next((i for i, t in enumerate(terms) if t.get("id") == "full"), len(terms))
                new_term = {"id": new_id, "label": f"Payment {len(terms)}", "amount": 0, "locked": False}
                st.session_state["payment_terms"].insert(pelunasan_idx, new_term)
                invalidate_pdf()
                st.rerun()
        
        # Action Buttons
        st.write("")
        # Dynamic logic for split buttons needing current grand total
        st.button(
            "Fill Remaining → Pelunasan",
            on_click=cb_fill_remaining_payment,
            args=(grand_total,),
            disabled=(grand_total <= 0),
            use_container_width=True,
        )
    # === TAB 2: PROOF ===
    with tab_proof:
        st.write("")
        
        current_proofs = st.session_state.get("pp_cached", [])
        is_editing = st.session_state.get("editing_invoice_id")
        
        # 1. ATTACHMENTS LIST - Only show for history (when editing)
        if current_proofs and is_editing:
            st.markdown(f"**Attachments ({len(current_proofs)})**")
            for idx, p in enumerate(current_proofs):
                if isinstance(p, dict):
                    c1, c2 = st.columns([0.85, 0.15])
                    with c1:
                        st.caption(f"📄 {p.get('name', 'File')} — {p.get('date', '')}")
                    with c2:
                        if st.button("✕", key=f"del_pp_{idx}"):
                            current_proofs.pop(idx)
                            st.session_state["pp_cached"] = current_proofs
                            st.rerun()
            st.divider()
        # 2. UPLOADER (Bottom)
        uploader_key = f"pp_uploader_{st.session_state.get('uploader_key', 0)}"
        pp_files = st.file_uploader(
            "Upload Images (Max 5MB)", 
            type=["jpg", "png", "jpeg"], 
            key=uploader_key, 
            accept_multiple_files=True,
            label_visibility="collapsed"
        )
        
        if pp_files:
            if not isinstance(current_proofs, list): 
                current_proofs = []
            
            new_added = False
            for f in pp_files:
                if f.size > 5 * 1024 * 1024:
                    st.error(f"❌ '{f.name}' too large.")
                    continue
                if any(p.get("name") == f.name for p in current_proofs):
                    continue
                    
                from modules.utils import image_to_base64
                b64 = image_to_base64(f)
                if b64:
                    current_proofs.append({
                        "name": f.name,
                        "b64": b64,
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                    new_added = True
                    st.toast(f"Attached: {f.name}", icon="📎")
            
            if new_added:
                st.session_state["pp_cached"] = current_proofs
                st.toast("Files attached!", icon="📎")
            
            # Don't reset uploader - let Streamlit's native preview persist
            # Files are already deduplicated, so re-runs won't duplicate
@st.dialog("📤 Kirim via WhatsApp")
def open_wa_dialog(wa_url: str):
    st.warning("⚠️ **PENTING**: File PDF **TIDAK** otomatis terkirim.")
    st.write("Silakan klik tombol di bawah untuk membuka chat, lalu **lampirkan file PDF** yang sudah Anda download secara manual.")
    st.write("")
    st.link_button("🚀 Lanjut ke WhatsApp", wa_url, use_container_width=True)
def render_action_buttons(subtotal: float, grand_total: float) -> None:
    st.write("")
    
    # Required field validation
    client_name = (st.session_state.get("inv_client_name") or "").strip()
    inv_no = (st.session_state.get("inv_no") or "").strip()
    venue = (st.session_state.get("inv_venue") or "").strip()
    client_phone = (st.session_state.get("inv_client_phone") or "").strip()
    event_title = (st.session_state.get("inv_title") or "").strip()
    
    missing_fields = []
    if not inv_no:
        missing_fields.append("**Invoice No**")
    # if not event_title:
    #     missing_fields.append("**Event Title**")
    if not client_name:
        missing_fields.append("**Client Name**")
    if not venue:
        missing_fields.append("**Venue**")
    # if not client_phone:
    #     missing_fields.append("**Client WhatsApp**")
    
    if missing_fields:
        st.warning(f"⚠️ Please fill in: {', '.join(missing_fields)}")
        st.button("📄 Generate Invoice PDF", type="primary", use_container_width=True, disabled=True)
    else:
        if st.button("📄 Generate Invoice PDF", type="primary", use_container_width=True):
            action_generate_pdf(subtotal, grand_total)
def render_download_section() -> None:
    pdf_data = st.session_state.get("generated_pdf_bytes")
    # Clean PDF bytes validation
    if not pdf_data:
        return
    try:
        if hasattr(pdf_data, "read"):
            pdf_data.seek(0)
            pdf_bytes = pdf_data.read()
        else:
            pdf_bytes = pdf_data if isinstance(pdf_data, (bytes, bytearray)) else b""
    except Exception:
        pdf_bytes = b""
    if not pdf_bytes:
        return
    inv_no = str(st.session_state.get("inv_no", "INV"))
    file_name = f"{make_safe_filename(inv_no, prefix='INV')}.pdf"
    
    # Determine Status Suffix (DP / LUNAS)
    payments = st.session_state.get("payment_terms", [])
    suffix = ""
    
    try:
        # Find "Pelunasan" (id='full')
        pelunasan = next((t for t in payments if t.get("id") == "full"), None)
        has_pelunasan = pelunasan and int(float(pelunasan.get("amount", 0))) > 0
        
        # Check DP (any term before Full that has amount > 0)
        has_dp = any(int(float(t.get("amount", 0))) > 0 for t in payments if t.get("id") != "full")
        
        if has_pelunasan:
            # If Pelunasan is filled, it's FULL/LUNAS
            # Check if there were other terms to distinguish "Direct Full" vs "Final Payment"
            # But simpler is better: if Pelunasan > 0 -> LUNAS
            suffix = "_LUNAS"
        elif has_dp:
            suffix = "_DP"
            
    except Exception:
        pass # Fallback to no suffix
        
    safe_base = make_safe_filename(inv_no, prefix='INV')
    file_name = f"{safe_base}{suffix}.pdf"
    
    with st.container(border=True):
        st.markdown("<div class='blk-title'>✅ PDF Ready</div>", unsafe_allow_html=True)
        
        col_dl, col_new = st.columns([2, 1])
        with col_dl:
            st.download_button(
                label="⬇️ Download PDF",
                data=pdf_bytes,
                file_name=file_name,
                mime="application/pdf",
                type="primary", 
                use_container_width=True
            )
            
            # --- ACTION BUTTONS (Restored) ---
            c_act1, c_act2 = st.columns(2)
            is_editing = st.session_state.get("editing_invoice_id")
            
            with c_act1:
                # Save / Update Logic
                if is_editing:
                    if st.button("💾 Update History", use_container_width=True):
                        handle_save_history(inv_no, is_update=True)
                else:
                    if st.button("💾 Save to History", use_container_width=True):
                        handle_save_history(inv_no, is_update=False)

            with c_act2:
                # WhatsApp Share Logic
                if st.button("📤 Share to WA", use_container_width=True):
                    # Prepare WA Link
                    client_name = st.session_state.get("inv_client_name", "-")
                    
                    # Get template
                    raw_tmpl = st.session_state.get("wa_template", "")
                    if not raw_tmpl:
                         raw_tmpl = db.get_config("wa_template_default") or "Halo {nama}, Invoice {inv_no} sudah ready."
                    
                    # Replace placeholders
                    msg = raw_tmpl.replace("{nama}", client_name).replace("{inv_no}", inv_no)
                    
                    # Encode
                    import urllib.parse
                    encoded_msg = urllib.parse.quote(msg)
                    
                    phone = st.session_state.get("inv_client_phone", "")
                    if phone.startswith("0"):
                        phone = "62" + phone[1:]
                    
                    wa_url = f"https://wa.me/{phone}?text={encoded_msg}"
                    open_wa_dialog(wa_url)

        with col_new:
            st.button("🆕 New Invoice", use_container_width=True, on_click=cb_reset_transaction)
