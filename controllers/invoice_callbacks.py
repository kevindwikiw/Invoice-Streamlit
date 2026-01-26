import streamlit as st
import json
from datetime import datetime, date
from uuid import uuid4
from typing import Any, Dict, List

from modules import db
# from modules import invoice as invoice_mod # Lazy load in action_generate_pdf to save RAM/Startup
from modules.invoice_state import (
    load_db_settings, 
    invalidate_pdf, 
    generate_invoice_no, 
    DEFAULT_FOOTER_ITEMS,
    DEFAULT_INVOICE_TITLE,
    DEFAULT_TERMS, 
    DEFAULT_BANK_INFO
)
from modules.utils import (
    safe_float, 
    safe_int, 
    normalize_desc_text, 
    desc_to_lines, 
    calculate_totals
)

# --- Constants for Callbacks ---
MIN_QTY = 1

# --- Helpers ---

def _cleanup_qty_keys_for_item(item: Dict[str, Any]) -> None:
    item_id = item.get("__id")
    if not item_id:
        return
    qty_key = f"qty_{item_id}"
    if qty_key in st.session_state:
        del st.session_state[qty_key]

def _cleanup_bundle_price_key_for_item(item: Dict[str, Any]) -> None:
    item_id = item.get("__id")
    if not item_id:
        return
    k = f"bundle_price_{item_id}"
    if k in st.session_state:
        del st.session_state[k]

def cleanup_all_qty_keys() -> None:
    for k in list(st.session_state.keys()):
        if str(k).startswith("qty_"):
            del st.session_state[k]

def cleanup_all_bundle_price_keys() -> None:
    for k in list(st.session_state.keys()):
        if str(k).startswith("bundle_price_"):
            del st.session_state[k]

def _cart_non_bundle_items() -> List[Dict[str, Any]]:
    out = []
    for it in st.session_state.get("inv_items", []):
        if not it.get("_bundle"):
            out.append(it)
    return out

def _cart_bundle_items() -> List[Dict[str, Any]]:
    out = []
    for it in st.session_state.get("inv_items", []):
        if it.get("_bundle"):
            out.append(it)
    return out

# --- Main Callbacks ---

def cb_update_invoice_no() -> None:
    """Callback to auto-generate invoice number when client name changes."""
    # Only auto-generate if not editing existing invoice
    if st.session_state.get("editing_invoice_id"):
        # For edits, increment revision
        current = st.session_state.get("inv_no", "")
        if current:
            import re
            match = re.match(r'(.*-)([0-9]+)$', current)
            if match:
                base, num = match.groups()
                st.session_state["inv_no"] = f"{base}{int(num)+1:03d}"
                invalidate_pdf()
                return
    
    # New invoice: generate fresh
    st.session_state["inv_no"] = generate_invoice_no()
    invalidate_pdf()

def cb_client_name_changed() -> None:
    """Updates Invoice No suffix when Client Name changes (if in draft mode)."""
    # 1. Invalidate PDF first
    invalidate_pdf()
    
    # 0. GUARD: Do NOT auto-change Invoice No if we are editing an existing invoice!
    # The user might be correcting a typo in the name, but we shouldn't change the Invoice ID.
    if st.session_state.get("editing_invoice_id"):
        return

    # 2. Get values
    client_name = st.session_state.get("inv_client_name", "").strip()
    current_no = st.session_state.get("inv_no", "").strip()
    
    # 3. Check if we should auto-update
    # Logic: If inv_no starts with 'INV' and digits, we append/replace suffix
    # e.g. INV001 -> INV001_RISA
    # e.g. INV001_OLD -> INV001_RISA
    # e.g. MY_CUSTOM_NO -> do nothing
    
    import re
    # Pattern: ^(INV\d+)(?:_.*)?$
    # Matches INV001 or INV001_ANYTHING
    match = re.match(r'^(INV\d+)(?:_.*)?$', current_no)
    
    if match and client_name:
        base_prefix = match.group(1) # e.g. INV001
        # Sanitized client name for ID (uppercase, unsafe chars removed)
        safe_suffix = "".join([c for c in client_name if c.isalnum() or c in (' ', '&', '-', '.')]).upper().strip()
        # safe_suffix = safe_suffix.replace(" ", "_") # User prefers spaces for readability
        
        # Limit suffix length?
        # Construct new ID
        new_no = f"{base_prefix}_{safe_suffix}"
        
        # Update state
        st.session_state["inv_no"] = new_no
        st.toast(f"Invoice No updated to: {new_no}", icon="🤖")

def cb_add_item_to_cart(package: Dict[str, Any]) -> None:
    try:
        row_id = str(package.get("id", package.get("name", ""))).strip()
        if not row_id:
            st.toast("Invalid item data.", icon="⚠️")
            return

        current_items = st.session_state["inv_items"]
        if any(str(item.get("_row_id")) == row_id for item in current_items):
            st.toast("Item already in cart!", icon="⚠️")
            return

        price = safe_float(package.get("price", 0))
        new_item = {
            "__id": str(uuid4()),
            "_row_id": row_id,
            "Description": str(package.get("name", "Unnamed")),
            "Details": str(package.get("description", "")),
            "Price": price,
            "Qty": 1,
            "Total": price,
        }

        st.session_state["inv_items"].append(new_item)
        invalidate_pdf()
        st.toast(f"Added: {new_item['Description']}", icon="🛒")
    except Exception as e:
        st.error(f"Failed to add item: {e}")

def cb_update_item_qty(item_id: str, widget_key: str) -> None:
    items = st.session_state["inv_items"]
    # Find item by ID
    found_idx = -1
    for i, it in enumerate(items):
        if str(it.get("__id")) == str(item_id):
            found_idx = i
            break
            
    if found_idx == -1:
        return

    item = items[found_idx]

    # Guard: bundle qty always 1
    if item.get("_bundle"):
        item["Qty"] = 1
        item["Total"] = safe_float(item.get("Price", 0)) * 1
        st.session_state[widget_key] = 1
        invalidate_pdf()
        return

    raw_value = st.session_state.get(widget_key, 1)
    new_qty = max(MIN_QTY, safe_int(raw_value, 1))

    item["Qty"] = new_qty
    item["Total"] = safe_float(item.get("Price", 0)) * new_qty
    invalidate_pdf()

def cb_delete_item(item_id: str) -> None:
    items = st.session_state["inv_items"]
    found_idx = -1
    for i, it in enumerate(items):
        if str(it.get("__id")) == str(item_id):
            found_idx = i
            break
            
    if found_idx == -1:
        return

    item = items[found_idx]
    _cleanup_qty_keys_for_item(item)
    _cleanup_bundle_price_key_for_item(item)
    items.pop(found_idx)
    invalidate_pdf()

def cb_delete_item_by_row_id(row_id: str) -> None:
    """Delete item from cart using the original Package ID (_row_id)."""
    items = st.session_state["inv_items"]
    found_idx = -1
    for i, it in enumerate(items):
        if str(it.get("_row_id")) == str(row_id):
            found_idx = i
            break
            
    if found_idx != -1:
        # Get actual UUID to clean up keys
        item = items[found_idx]
        _cleanup_qty_keys_for_item(item)
        items.pop(found_idx)
        invalidate_pdf()
        st.toast("Packet removed!", icon="🗑️")

def cb_update_bundle_price(item_id: str, widget_key: str) -> None:
    items = st.session_state["inv_items"]
    item = None
    for it in items:
        if str(it.get("__id")) == str(item_id):
            item = it
            break
            
    if not item or not item.get("_bundle"):
        return

    v = max(0, safe_int(st.session_state.get(widget_key, 0), 0))
    item["Price"] = float(v)
    item["Qty"] = 1
    item["Total"] = float(v)
    invalidate_pdf()



def cb_fill_remaining_payment(grand_total: float) -> None:
    if grand_total <= 0:
        return

    terms = st.session_state.get("payment_terms", [])
    if not terms:
        return

    # Find "full" term index
    full_idx = -1
    for i, t in enumerate(terms):
        if t.get("id") == "full":
            full_idx = i
            break
            
    if full_idx == -1:
         st.toast("Pelunasan term not found.", icon="⚠️")
         return

    # Sum all OTHER terms
    current_paid = 0
    for i, t in enumerate(terms):
        if i != full_idx:
            current_paid += safe_int(t.get("amount", 0), 0)

    remaining = max(0, int(grand_total) - current_paid)
    
    # Update term list
    terms[full_idx]["amount"] = remaining
    
    # Update widget key if exists (to reflect in UI immediately)
    full_key = "pay_amt_full"
    if full_key in st.session_state:
        st.session_state[full_key] = remaining
        
    st.session_state["payment_terms"] = terms
    invalidate_pdf()
    st.toast("Remaining balance added to Pelunasan.", icon="✅")

def cb_reset_transaction() -> None:
    st.session_state["inv_items"] = []
    # Use pop() for widget-bound keys to avoid "cannot be modified after instantiation" error
    st.session_state.pop("inv_cashback", None)
    st.session_state["generated_pdf_bytes"] = None
    st.session_state["pp_cached"] = []  # Clear Payment Proofs
    
    # Clear Metadata - use pop() for widget-bound keys
    db_conf = load_db_settings()
    st.session_state.pop("inv_title", None)
    st.session_state["_default_inv_title"] = db_conf["title"]
    
    # Reload Configs (FORCE RESET to Global Defaults)
    st.session_state["inv_terms"] = db_conf["terms"]
    st.session_state["_default_inv_terms"] = db_conf["terms"]
    
    st.session_state["bank_nm"] = db_conf["bank_nm"]
    st.session_state["_default_bank_nm"] = db_conf["bank_nm"]
    
    st.session_state["bank_ac"] = db_conf["bank_ac"]
    st.session_state["_default_bank_ac"] = db_conf["bank_ac"]
    
    st.session_state["bank_an"] = db_conf["bank_an"]
    st.session_state["_default_bank_an"] = db_conf["bank_an"]
    
    st.session_state["inv_footer"] = db_conf["inv_footer"]
    st.session_state["_default_inv_footer"] = db_conf["inv_footer"]
    
    # WA Template needs special handling as it might not be in db_conf dict directly if not loaded by load_db_settings main query
    st.session_state.pop("wa_template", None) 

    st.session_state.pop("inv_client_name", None)
    st.session_state.pop("inv_client_phone", None)
    st.session_state.pop("inv_client_email", None)
    st.session_state.pop("inv_venue", None)
    st.session_state.pop("inv_wedding_date", None)
    st.session_state.pop("inv_no", None)
    st.session_state.pop("_draft_global_seq", None)  # Force re-fetch of next sequence
    
    st.session_state["payment_terms"] = [
        {"id": "dp", "label": "Down Payment", "amount": 0, "locked": True},
        {"id": "full", "label": "Pelunasan", "amount": 0, "locked": True},
    ]
    st.session_state["editing_invoice_id"] = None  # Clear edit mode
    cleanup_all_qty_keys()
    cleanup_all_bundle_price_keys()
    
    # Reset file uploader widget by changing its key
    st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1
    
    # Force refresh to close popover and scroll to top
    st.session_state["nav_key"] = st.session_state.get("nav_key", 0) + 1
    st.session_state["_needs_rerun"] = True

def cb_merge_selected_from_ui() -> None:
    sel_ids: List[str] = st.session_state.get("bundle_sel", []) or []
    sel_ids = [str(x) for x in sel_ids if str(x)]
    if len(sel_ids) < 2:
        st.toast("Select at least 2 items to merge.", icon="⚠️")
        return

    # map id -> item
    items = st.session_state.get("inv_items", [])
    id_to_item = {str(it.get("__id")): it for it in items}

    selected: List[Dict[str, Any]] = []
    for sid in sel_ids:
        it = id_to_item.get(sid)
        if not it:
            continue
        if it.get("_bundle"):
            st.toast("Cannot merge a bundle item.", icon="⚠️")
            return
        selected.append(it)

    if len(selected) < 2:
        st.toast("Selected items not found.", icon="⚠️")
        return

    # default title
    title = (st.session_state.get("bundle_title") or "").strip()
    if not title:
        # auto title "A + B + C"
        names = [str(x.get("Description", "")).strip() for x in selected]
        names = [n for n in names if n]
        title = "Bundling: " + " + ".join(names[:3]) + ("..." if len(names) > 3 else "")

    mode = st.session_state.get("bundle_price_mode") or "Sum of selected"
    if mode == "Custom":
        price = float(max(0, safe_int(st.session_state.get("bundle_custom_price", 0), 0)))
    else:
        # Sum of selected (respect qty)
        price = 0.0
        for it in selected:
            price += safe_float(it.get("Price", 0)) * max(1, safe_int(it.get("Qty", 1), 1))

    # merged details
    merged_lines: List[str] = []
    for it in selected:
        nm = str(it.get("Description", "")).strip()
        if nm:
            merged_lines.append(nm)
        det = normalize_desc_text(it.get("Details", ""))
        det_lines = desc_to_lines(det)
        for ln in det_lines:
            merged_lines.append(f"- {ln}")
        merged_lines.append("")  # spacer
    merged_details = "\n".join([x for x in merged_lines]).strip()

    # remove selected from cart
    remaining: List[Dict[str, Any]] = []
    selected_id_set = set(sel_ids)
    for it in st.session_state["inv_items"]:
        if str(it.get("__id")) in selected_id_set:
            _cleanup_qty_keys_for_item(it)
            _cleanup_bundle_price_key_for_item(it)
        else:
            remaining.append(it)

    # bundle item
    bundle_item = {
        "__id": str(uuid4()),
        "_row_id": "bundle:" + str(uuid4()),
        "Description": title,
        "Details": merged_details,
        "Price": float(price),
        "Qty": 1,
        "Total": float(price),
        "_bundle": True,
        "_bundle_src": [dict(x) for x in selected],  # store shallow copies for unmerge
    }

    st.session_state["inv_items"] = remaining + [bundle_item]

    # reset UI selection
    st.session_state["bundle_sel"] = []
    st.session_state["bundle_title"] = ""
    st.session_state["bundle_custom_price"] = 0

    invalidate_pdf()
    st.toast("Bundling created.", icon="✅")

def cb_unmerge_bundle(bundle_id: str) -> None:
    bundle_id = str(bundle_id)
    items = st.session_state.get("inv_items", [])
    new_items: List[Dict[str, Any]] = []
    restored: List[Dict[str, Any]] = []

    for it in items:
        if str(it.get("__id")) == bundle_id and it.get("_bundle"):
            restored = it.get("_bundle_src") or []
            _cleanup_qty_keys_for_item(it)
            _cleanup_bundle_price_key_for_item(it)
        else:
            new_items.append(it)

    if not restored:
        st.toast("Nothing to unmerge.", icon="ℹ️")
        return

    # restore original items (make sure they still have required keys)
    for r in restored:
        # If something misses __id (shouldn't), re-add
        if "__id" not in r or not str(r.get("__id")):
            r["__id"] = str(uuid4())
        # ensure Total consistent
        qty = max(1, safe_int(r.get("Qty", 1), 1))
        r["Qty"] = qty
        r["Total"] = safe_float(r.get("Price", 0)) * qty
        # remove bundle metadata if any
        if "_bundle" in r:
            del r["_bundle"]
        if "_bundle_src" in r:
            del r["_bundle_src"]

    st.session_state["inv_items"] = new_items + restored
    invalidate_pdf()
    st.toast("Bundling reverted.", icon="↩️")

def _sync_payment_terms_from_ui() -> None:
    """Manually sync widget values to payment_terms list before saving/generating."""
    terms = st.session_state.get("payment_terms", [])
    for i, term in enumerate(terms):
        term_id = term.get("id", f"term_{i}")
        # Sync Amount
        amt_key = f"pay_amt_{term_id}"
        if amt_key in st.session_state:
            terms[i]["amount"] = int(st.session_state[amt_key])
        
        # Sync Label (custom terms only)
        label_key = f"pay_label_{term_id}"
        if label_key in st.session_state and not term.get("locked"):
            terms[i]["label"] = st.session_state[label_key]
    
    st.session_state["payment_terms"] = terms

def handle_save_history(inv_no: str, is_update: bool = False) -> None:
    """Save invoice to database history with PDF blob."""
    try:
        # Retrieve context from session state
        client_email = st.session_state.get("inv_client_email", "")
        pdf_bytes = st.session_state.get("generated_pdf_bytes")

        # 0. Sync UI values first! (Critical for callbacks)
        _sync_payment_terms_from_ui()

        # 0. Normalize pdf_bytes to raw bytes
        pdf_blob = None
        if pdf_bytes:
            if hasattr(pdf_bytes, 'read'):
                pdf_bytes.seek(0)
                pdf_blob = pdf_bytes.read()
            elif isinstance(pdf_bytes, (bytes, bytearray)):
                pdf_blob = bytes(pdf_bytes)
        
        # 1. Gather Data
        meta = {
            "inv_no": st.session_state.get("inv_no", ""),
            "title": st.session_state.get("inv_title", ""),
            "date": datetime.now().strftime("%d %B %Y"),
            "client_name": st.session_state.get("inv_client_name", ""),
            "client_phone": st.session_state.get("inv_client_phone", ""),
            "client_email": client_email,
            "wedding_date": (st.session_state.get("inv_wedding_date") or date.today()).strftime("%d %B %Y"),
            "venue": st.session_state.get("inv_venue", ""),
            "subtotal": 0,
            "cashback": safe_float(st.session_state.get("inv_cashback", 0)),
            "payment_terms": st.session_state.get("payment_terms", []),
            "terms": st.session_state.get("inv_terms", ""),
            "bank_name": st.session_state.get("bank_nm", ""),
            "bank_acc": st.session_state.get("bank_ac", ""),
            "bank_holder": st.session_state.get("bank_an", ""),
            "payment_proof": st.session_state.get("pp_cached") or [],
            "footer_info": [x.strip() for x in str(st.session_state.get("inv_footer", "")).split("\n") if x.strip()]
        }

        # Format Wedding date to English for DB meta (consistent with generation)
        w_date = st.session_state.get("inv_wedding_date")
        if w_date:
            meta["wedding_date"] = w_date.strftime("%A, %d %B %Y")
        else:
            meta["wedding_date"] = ""
        
        # Recalc Totals for DB
        items = st.session_state.get("inv_items", [])
        sub, grand = calculate_totals(items, meta["cashback"])
        meta["subtotal"] = sub
        
        payload = {
            "meta": meta,
            "items": items,
            "grand_total": grand
        }
        
        # 2. Save or Update
        edit_id = st.session_state.get("editing_invoice_id")
        
        if edit_id:
            db.update_invoice(
                edit_id,
                inv_no, 
                meta["client_name"], 
                date.today().strftime("%Y-%m-%d"), 
                grand, 
                json.dumps(payload),
                pdf_blob=pdf_blob
            )
            st.toast("Updated! Redirecting to History...", icon="✅")
            st.session_state["editing_invoice_id"] = None
            
        else:
            db.save_invoice(
                inv_no, 
                meta["client_name"], 
                date.today().strftime("%Y-%m-%d"), 
                grand, 
                json.dumps(payload),
                pdf_blob=pdf_blob
            )
            st.toast("Invoice saved! Redirecting to History...", icon="💾")
            
            # Check if we need to update global sequence
            # ONLY for NEW invoices (not edits)
            if not st.session_state.get("editing_invoice_id"):
                # Try parse numeric part from inv_no (e.g. INV00123)
                # This ensures next person gets INV00124
                import re
                m = re.search(r'(\d+)', inv_no)
                if m:
                    used_num = int(m.group(1))
                    db.update_global_sequence_if_needed(used_num)
        
        # Reset form and set redirect flag (will be handled outside callback)
        cb_reset_transaction()
        st.session_state["menu_selection"] = "📜 Invoice History"
        st.session_state["nav_key"] = st.session_state.get("nav_key", 0) + 1
        st.session_state["_redirect_to_history"] = True
        st.rerun() # Force redirect immediately
            
    except Exception as e:
        import traceback
        st.error(f"Failed to save/update history: {e}")
        st.code(traceback.format_exc())  # Show stack trace for debugging

def action_generate_pdf(subtotal: float, grand_total: float) -> None:
    try:
        # Sync UI first!
        _sync_payment_terms_from_ui()

        meta = {
            "inv_no": st.session_state.get("inv_no", ""),
            "title": st.session_state.get("inv_title", "Invoice"),
            "date": datetime.now().strftime("%d %B %Y"),
            "client_name": st.session_state.get("inv_client_name", ""),
            "wedding_date": (st.session_state.get("inv_wedding_date") or date.today()).strftime("%d %B %Y"),
            "venue": st.session_state.get("inv_venue", ""),
            "subtotal": subtotal,
            "cashback": st.session_state.get("inv_cashback", 0),
            "payment_terms": st.session_state.get("payment_terms", []),
            "terms": st.session_state.get("inv_terms", ""),
            "bank_name": st.session_state.get("bank_nm", ""),
            "bank_acc": st.session_state.get("bank_ac", ""),
            "bank_holder": st.session_state.get("bank_an", ""),
            "payment_proof": st.session_state.get("pp_cached") or [],
            "footer_info": [x.strip() for x in str(st.session_state.get("inv_footer", "")).split("\n") if x.strip()]
        }
        
        # Format Wedding date to English: "Sunday, 12 January 2026"
        w_date = st.session_state.get("inv_wedding_date")
        if w_date:
            meta["wedding_date"] = w_date.strftime("%A, %d %B %Y")
        else:
            meta["wedding_date"] = ""

        with st.spinner("Generating PDF..."):
            # Lazy Import for Performance (Load bulky PDF libs only when needed)
            from modules import invoice as invoice_mod
            pdf_bytes = invoice_mod.generate_pdf_bytes(meta, st.session_state["inv_items"], grand_total)

        if not pdf_bytes:
            raise ValueError("PDF Generator returned empty data.")

        st.session_state["generated_pdf_bytes"] = pdf_bytes
        st.toast("PDF Generated Successfully!", icon="✅")

    except Exception as e:
        st.session_state["generated_pdf_bytes"] = None
        st.error(f"Error generating PDF: {e}")

def cb_save_defaults() -> None:
    """Saves current form values as new system defaults."""
    from modules import db
    from modules.invoice_state import load_db_settings
    
    # Save to DB
    updates = {
        "inv_title_default": st.session_state.get("inv_title", ""),
        "inv_terms_default": st.session_state.get("inv_terms", ""),
        "bank_nm_default": st.session_state.get("bank_nm", ""),
        "bank_ac_default": st.session_state.get("bank_ac", ""),
        "bank_an_default": st.session_state.get("bank_an", ""),
        "inv_footer_default": st.session_state.get("inv_footer", ""),
        "wa_template_default": st.session_state.get("wa_template", ""),
    }
    
    for k, v in updates.items():
        if v:
            db.set_config(k, v)
            
    # Clear Cache
    load_db_settings.clear()
    
    st.toast("Settings saved as new defaults!", icon="💾")
