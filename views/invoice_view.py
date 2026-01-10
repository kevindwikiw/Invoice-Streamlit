# invoice_view.py
from __future__ import annotations

import io
import streamlit as st
from uuid import uuid4
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Tuple

# --- Internal Modules ---
from modules import db
from modules import invoice as invoice_mod
from modules import gdrive
from modules.utils import (
    safe_float, safe_int, normalize_db_records, calculate_totals,
    sanitize_text, desc_to_lines, normalize_desc_text, 
    is_valid_email, make_safe_filename, image_to_base64
)

# --- UI Components ---
from ui.components import page_header
from ui.formatters import rupiah
from views.styles import inject_styles, POS_COLUMN_RATIOS

# --- Fallback Logic for Tooltips ---
try:
    from views.packages_view import _desc_meta, CATEGORIES  # type: ignore
except ImportError:
    CATEGORIES = ["Utama", "Bonus"]

    def _desc_meta(text: str, max_lines: int = 2) -> Tuple[str, str, List[str]]:
        """Parses description text into a preview and bullet points."""
        text = (text or "").strip()
        if not text:
            return "", "", []
        lines = [x.strip("-• ").strip() for x in text.split("\n") if x.strip()]
        preview = " · ".join(lines[:max_lines]) if lines else text[:80]
        return preview, "", lines


# ==============================================================================
# 1) CONFIGURATION & CONSTANTS
# ==============================================================================

# Recommended: keep Desc not too dominant, Qty compact, Total readable, Del not bengkeng
# POS_COLUMN_RATIOS moved to views.styles
MIN_QTY = 1

CASHBACK_STEP = 500_000
PAYMENT_STEP = 1_000_000
BUNDLE_PRICE_STEP = 500_000

DEFAULT_INVOICE_TITLE = ""
DEFAULT_TERMS = (
    "Down Payment sebesar Rp 500.000 (Lima Ratus Ribu Rupiah) saat di booth pameran\n"
    "Termin pembayaran H+7 Pameran: Rp 500.000, H-7 prewedding: Rp 3.000.000, dan pelunasan H-7 wedding\n"
    "Maksimal pembayaran Invoice 1 minggu dari tanggal invoice\n"
    "Paket yang telah dipilih tidak bisa down grade\n"
    "Melakukan pembayaran berarti menyatakan setuju dengan detail invoice. Pembayaran yang telah dilakukan tidak bisa di refund"
)
DEFAULT_BANK_INFO = {
    "bank_nm": "OCBC",
    "bank_ac": "693810505794",
    "bank_an": "FANI PUSPITA NINGRUM",
}

# --- DB Persistence Helper ---
def load_db_settings() -> Dict[str, Any]:
    return {
        "title": db.get_config("inv_title_default", DEFAULT_INVOICE_TITLE),
        "terms": db.get_config("inv_terms_default", DEFAULT_TERMS),
        "bank_nm": db.get_config("bank_nm_default", DEFAULT_BANK_INFO["bank_nm"]),
        "bank_ac": db.get_config("bank_ac_default", DEFAULT_BANK_INFO["bank_ac"]),
        "bank_an": db.get_config("bank_an_default", DEFAULT_BANK_INFO["bank_an"]),
    }

# --- DB Persistence Helper ---
def load_db_settings() -> Dict[str, Any]:
    return {
        "title": db.get_config("inv_title_default", DEFAULT_INVOICE_TITLE),
        "terms": db.get_config("inv_terms_default", DEFAULT_TERMS),
        "bank_nm": db.get_config("bank_nm_default", DEFAULT_BANK_INFO["bank_nm"]),
        "bank_ac": db.get_config("bank_ac_default", DEFAULT_BANK_INFO["bank_ac"]),
        "bank_an": db.get_config("bank_an_default", DEFAULT_BANK_INFO["bank_an"]),
    }

CATALOG_CACHE_TTL_SEC = 300  # 5 min, safe default


# ==============================================================================
# 2) STYLING (CSS)
# ==============================================================================

# ==============================================================================
# 2) STYLING (CSS) - Moved to views/styles.py
# ==============================================================================
# injected via inject_styles() call


# ==============================================================================
# 3) HELPERS (minimal, no extra imports)
# ==============================================================================

def _image_to_base64(uploaded_file) -> str:
    """Wrapper for backward compatibility or direct import."""
    return image_to_base64(uploaded_file)

# --- Removed extracted helpers ---

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


# ==============================================================================
# 4) DATA ACCESS (cached)
# ==============================================================================

@st.cache_data(show_spinner=False, ttl=CATALOG_CACHE_TTL_SEC)
def load_packages_cached() -> List[Dict[str, Any]]:
    raw = db.load_packages()
    return normalize_db_records(raw)


# ==============================================================================
# 5) STATE MANAGEMENT (Streamlit-dependent)
# ==============================================================================

def initialize_session_state() -> None:
    # Load custom defaults from DB
    db_conf = load_db_settings()

    defaults: Dict[str, Any] = {
        # Cart Data
        "inv_items": [],
        "inv_cashback": 0,
        "generated_pdf_bytes": None,

        # Invoice Metadata
        "inv_title": db_conf["title"],
        "inv_no": f"INV/{datetime.now().strftime('%m')}/2026",
        "inv_client_name": "",
        "inv_client_email": "",
        "inv_wedding_date": date.today() + timedelta(days=90),
        "inv_venue": "",

        # Payment Schedule
        "pay_dp1": 0,
        "pay_term2": 0,
        "pay_term3": 0,
        "pay_full": 0,

        # Configs
        "inv_terms": db_conf["terms"],
        "bank_nm": db_conf["bank_nm"],
        "bank_ac": db_conf["bank_ac"],
        "bank_an": db_conf["bank_an"],

        # UI Filters
        "cat_filter": "All",
        "sort_filter": "Price: High",
        "search_filter": "",

        # Bundling UI state
        "bundle_sel": [],
        "bundle_title": "",
        "bundle_price_mode": "Sum of selected",
        "bundle_custom_price": 0,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)
        
    # Ensure editing ID exists
    st.session_state.setdefault("editing_invoice_id", None)

def invalidate_pdf() -> None:
    st.session_state["generated_pdf_bytes"] = None

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



# --- Invoice Number Generator ---

def _sanitize_client_name(name: str) -> str:
    """Extract clean uppercase identifier from client name."""
    import re
    # Remove special chars, keep only letters/numbers
    clean = re.sub(r'[^a-zA-Z0-9]', '', name)
    # Take first 12 chars uppercase
    return clean[:12].upper() if clean else ""

def generate_invoice_no() -> str:
    """Generate invoice number based on client name with DB-backed sequence."""
    client_name = st.session_state.get("inv_client_name", "").strip()
    
    if not client_name:
        # Fallback to date-based
        prefix = datetime.now().strftime('%Y%m%d')
    else:
        prefix = _sanitize_client_name(client_name)
        if not prefix:
            prefix = datetime.now().strftime('%Y%m%d')
    
    # Get next sequence from DB (atomic increment)
    seq = db.get_next_invoice_seq(prefix)
    
    return f"INV-{prefix}-{seq:03d}"

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

# --- Callbacks ---

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

def cb_auto_split_payments(grand_total: float) -> None:
    if grand_total <= 0:
        return

    q = int(grand_total // 4)
    st.session_state["pay_dp1"] = q
    st.session_state["pay_term2"] = q
    st.session_state["pay_term3"] = q
    st.session_state["pay_full"] = int(grand_total - (q * 3))
    invalidate_pdf()
    st.toast("Payments split evenly (4 terms).", icon="✅")

def cb_fill_remaining_payment(grand_total: float) -> None:
    if grand_total <= 0:
        return

    current_paid = (
        safe_int(st.session_state.get("pay_dp1", 0), 0)
        + safe_int(st.session_state.get("pay_term2", 0), 0)
        + safe_int(st.session_state.get("pay_term3", 0), 0)
    )
    remaining = max(0, int(grand_total) - current_paid)
    st.session_state["pay_full"] = remaining
    invalidate_pdf()
    st.toast("Remaining balance added to Pelunasan.", icon="✅")

def cb_reset_transaction() -> None:
    st.session_state["inv_items"] = []
    st.session_state["inv_cashback"] = 0
    st.session_state["generated_pdf_bytes"] = None
    st.session_state["pp_cached"] = []  # Clear Payment Proofs
    
    # Clear Metadata
    db_conf = load_db_settings()
    st.session_state["inv_title"] = db_conf["title"]
    st.session_state["inv_client_name"] = ""
    st.session_state["inv_client_email"] = ""
    st.session_state["inv_venue"] = ""
    st.session_state["inv_wedding_date"] = date.today() + timedelta(days=90)
    # Default Invoice No (Auto-gen for next ID usually better, here simplistic)
    st.session_state["inv_no"] = f"INV/{datetime.now().strftime('%m')}/2026"
    
    st.session_state["pay_dp1"] = 0
    st.session_state["pay_term2"] = 0
    st.session_state["pay_term3"] = 0
    st.session_state["pay_full"] = 0
    st.session_state["editing_invoice_id"] = None  # Clear edit mode
    cleanup_all_qty_keys()
    cleanup_all_bundle_price_keys()
    
    # Reset file uploader widget by changing its key
    st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1
    
    # Force scroll to top by incrementing nav_key
    st.session_state["nav_key"] = st.session_state.get("nav_key", 0) + 1
    
    st.toast("Form reset! Starting fresh.", icon="🆕")

# --- Bundling callbacks ---

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


# ==============================================================================
# 6) UI RENDERERS
# ==============================================================================

def render_event_metadata() -> None:
    # --- Card 1: Event & Client ---
    st.markdown(
        """
        <div class="iso-card">
            <div class="iso-row" style="margin-bottom:12px;">
                <div class="blk-title" style="margin:0;">📝 Event Details</div>
            </div>
        """, 
        unsafe_allow_html=True
    )
    
    # Event Row - symmetric columns
    c1, c2, c3 = st.columns([1, 1, 1])
    c1.text_input("Invoice No", key="inv_no", on_change=invalidate_pdf)
    c2.date_input("Wedding Date", key="inv_wedding_date", on_change=invalidate_pdf)
    c3.text_input("Venue", key="inv_venue", placeholder="Hotel/Gedung", on_change=invalidate_pdf)
    
    st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
    
    # Client Row - symmetric columns
    c4, c5, c6 = st.columns([1, 1, 1])
    c4.text_input("Event / Title", key="inv_title", placeholder="e.g. Wedding Reception 2026", on_change=invalidate_pdf)
    c5.text_input("Client Name", key="inv_client_name", placeholder="CPW & CPP", on_change=cb_update_invoice_no)
    c6.text_input("Email", key="inv_client_email", placeholder="client@email.com", on_change=invalidate_pdf)
    
    st.markdown("</div>", unsafe_allow_html=True) # End Card 1

    # Banking Config (Collapsible) - Moved here to reduce Right Col height
    with st.expander("🏦 Bank & Terms Config"):
        b_col1, b_col2, b_col3 = st.columns(3)
        b_col1.text_input("Bank Name", key="bank_nm", on_change=invalidate_pdf)
        b_col2.text_input("Account No", key="bank_ac", on_change=invalidate_pdf)
        b_col3.text_input("Account Holder", key="bank_an", on_change=invalidate_pdf)
        
        st.text_area("Terms & Conditions", key="inv_terms", height=100, on_change=invalidate_pdf)
        
        if st.button("💾 Save Settings", help="Save as defaults", use_container_width=True):
            db.set_config("bank_nm_default", st.session_state["bank_nm"])
            db.set_config("bank_ac_default", st.session_state["bank_ac"])
            db.set_config("bank_an_default", st.session_state["bank_an"])
            db.set_config("inv_terms_default", st.session_state["inv_terms"])
            st.toast("Settings saved!", icon="✅")


def render_payment_section(grand_total: float) -> None:
    # --- Card 2: Payment Schedule ---
    st.markdown(
        """
        <div class="iso-card">
            <div class="iso-row" style="margin-bottom:12px;">
                <div class="blk-title" style="margin:0;">💸 Payment Schedule</div>
            </div>
        """,
        unsafe_allow_html=True
    )

    dp1 = safe_int(st.session_state.get("pay_dp1", 0), 0)
    t2 = safe_int(st.session_state.get("pay_term2", 0), 0)
    t3 = safe_int(st.session_state.get("pay_term3", 0), 0)
    full = safe_int(st.session_state.get("pay_full", 0), 0)

    status, msg, _ = payment_integrity_status(grand_total, dp1, t2, t3, full)

    if status == "BALANCED":
        badge_cls = "badg-green"
    elif status == "UNALLOCATED":
        badge_cls = "badg-orange" 
    elif status == "OVER":
        badge_cls = "badg-red"
    else:
        badge_cls = "badg-blue"

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

    # Input Grid with formatted captions
    row1, row2, row3, row4 = st.columns(4)
    
    with row1:
        st.number_input("DP 1", step=PAYMENT_STEP, key="pay_dp1", on_change=invalidate_pdf)
        dp1_val = safe_int(st.session_state.get("pay_dp1", 0))
        if dp1_val > 0:
            st.caption(f"Rp {dp1_val:,}".replace(",", "."))
    
    with row2:
        st.number_input("Term 2", step=PAYMENT_STEP, key="pay_term2", on_change=invalidate_pdf)
        t2_val = safe_int(st.session_state.get("pay_term2", 0))
        if t2_val > 0:
            st.caption(f"Rp {t2_val:,}".replace(",", "."))
    
    with row3:
        st.number_input("Term 3", step=PAYMENT_STEP, key="pay_term3", on_change=invalidate_pdf)
        t3_val = safe_int(st.session_state.get("pay_term3", 0))
        if t3_val > 0:
            st.caption(f"Rp {t3_val:,}".replace(",", "."))
    
    with row4:
        st.number_input("Pelunasan", step=PAYMENT_STEP, key="pay_full", on_change=invalidate_pdf)
        full_val = safe_int(st.session_state.get("pay_full", 0))
        if full_val > 0:
            st.caption(f"Rp {full_val:,}".replace(",", "."))

    # Buttons
    st.write("")
    btn_col1, btn_col2 = st.columns(2)
    btn_col1.button(
        "Auto Split 4",
        on_click=cb_auto_split_payments,
        args=(grand_total,),
        disabled=(grand_total <= 0),
        use_container_width=True,
    )
    btn_col2.button(
        "Fill Remaining → Pelunasan",
        on_click=cb_fill_remaining_payment,
        args=(grand_total,),
        disabled=(grand_total <= 0),
        use_container_width=True,
    )

    st.markdown("</div>", unsafe_allow_html=True) # End Card 2

    # --- Card 3: Payment Proof ---
    st.markdown(
        """
        <div class="iso-card">
            <div class="iso-row">
                <div class="blk-title" style="margin:0;">📸 Payment Proof</div>
            </div>
            <div style="margin-top:12px;"></div>
        """,
        unsafe_allow_html=True
    )
    
    pp_col1, pp_col2 = st.columns([3, 1])
    with pp_col1:
        # Dynamic key ensures uploader resets when form is reset
        uploader_key = f"pp_uploader_{st.session_state.get('uploader_key', 0)}"
        pp_files = st.file_uploader(
            "Upload Images (Max 5MB each)", 
            type=["jpg", "png", "jpeg"], 
            key=uploader_key, 
            accept_multiple_files=True,
            label_visibility="collapsed"
        )
    
    if pp_files:
        # Check if list exists
        current_proofs = st.session_state.get("pp_cached", [])
        if not isinstance(current_proofs, list):
             current_proofs = []
             
        new_added = False
        for f in pp_files:
            # Basic Error Handling: Size Limit (5MB)
            if f.size > 5 * 1024 * 1024:
                st.error(f"❌ '{f.name}' is too large (>5MB). Skipped.")
                continue
                
            try:
                # Convert to base64
                b64 = _image_to_base64(f)
                # Avoid duplicates (basic check)
                if b64 not in current_proofs:
                    current_proofs.append(b64)
                    new_added = True
            except Exception as e:
                st.error(f"Error processing '{f.name}': {e}")
                
        if new_added:
            st.session_state["pp_cached"] = current_proofs
        
    with pp_col2:
        cached = st.session_state.get("pp_cached")
        if cached:
            if isinstance(cached, list):
                cnt = len(cached)
                st.success(f"{cnt} Files Ready!")
            else:
                st.success("1 File Ready!")
                
            # Clear All Callback - also reset uploader widget
            def _cb_clear_proof():
                st.session_state["pp_cached"] = []
                st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1
                
            if st.button("❌ Clear All", key="rm_proof", type="secondary", use_container_width=True, on_click=_cb_clear_proof):
                pass
    
    st.markdown("</div>", unsafe_allow_html=True) # End Card 3

    # --- PROCESS ACTIONS ---
    st.write("")
    act_col1, act_col2 = st.columns([1, 2], vertical_alignment="bottom")
    
    # 1. Reset Confirmation Popover
    with act_col1.popover("Reset All", use_container_width=True):
        st.write("Are you sure?")
        if st.button("Yes, Reset!", type="primary", use_container_width=True, on_click=cb_reset_transaction):
            pass # changes happen in callback

    # Re-calculate checks for button state
    # We need subtotal/grand_total but they are passed to parent. 
    # Wait, simple check: items > 0 and grand_total passed in arg > 0
    items = st.session_state.get("inv_items", [])
    is_valid_order = (len(items) > 0) and (grand_total > 0)
    already_ready = bool(st.session_state.get("generated_pdf_bytes"))
    
    btn_label = "✅ PDF Ready" if already_ready else "🚀 Process Invoice & PDF"
    
    # We need subtotal for generate_pdf_wrapper. 
    # Use utils/calculate_totals helper to re-derive subtotal from items.
    # OR, we should pass subtotal to this function. 
    # For now, re-calculating is safe and cheap.
    current_sub, _ = calculate_totals(items, safe_float(st.session_state.get("inv_cashback", 0)))

    # Check if PDF already generated
    pdf_bytes = st.session_state.get("generated_pdf_bytes")
    
    if pdf_bytes:
        # --- PDF Ready: Show all action options ---
        st.success("✅ PDF Generated!")
        
        inv_no = st.session_state.get("inv_no", "invoice").replace("/", "_")
        client_email = (st.session_state.get("inv_client_email") or "").strip()
        
        # Row 1: Download + Re-process
        dl_col, re_col = st.columns(2)
        with dl_col:
            st.download_button(
                "📥 Download PDF",
                data=pdf_bytes,
                file_name=f"{inv_no}.pdf",
                mime="application/pdf",
                use_container_width=True,
                type="primary"
            )
        with re_col:
            if st.button("🔄 Re-process PDF", use_container_width=True, disabled=not is_valid_order):
                invalidate_pdf()  # Clear current PDF
                generate_pdf_wrapper(current_sub, grand_total)
                st.rerun()
        
        # Row 2: Save to History + Start New
        save_col, new_col = st.columns(2)
        
        edit_id = st.session_state.get("editing_invoice_id")
        save_label = f"💾 Update (#{edit_id})" if edit_id else "💾 Save to History"
        
        with save_col:
            if st.button(save_label, use_container_width=True, on_click=_handle_save_history, args=(inv_no, client_email, pdf_bytes)):
                pass
        with new_col:
            if st.button("🆕 New Invoice", use_container_width=True, on_click=cb_reset_transaction):
                pass
    else:
        # --- No PDF yet: Show Process button ---
        if act_col2.button("🚀 Process Invoice & PDF", type="primary", use_container_width=True, disabled=not is_valid_order):
            generate_pdf_wrapper(current_sub, grand_total)
            st.rerun()

def _filter_and_sort_packages(packages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cat_filter = st.session_state.get("cat_filter", "All")
    sort_filter = st.session_state.get("sort_filter", "Price: High")
    search_query = (st.session_state.get("search_filter", "") or "").lower().strip()

    filtered = list(packages)

    if cat_filter != "All":
        filtered = [p for p in filtered if p.get("category") == cat_filter]

    if search_query:
        filtered = [p for p in filtered if search_query in str(p.get("name", "")).lower()]

    if sort_filter == "Price: Low":
        filtered.sort(key=lambda x: safe_float(x.get("price")))
    else:
        filtered.sort(key=lambda x: safe_float(x.get("price")), reverse=True)

    return filtered

def render_catalog_section(packages: List[Dict[str, Any]]) -> None:
    # --- Catalog Card ---
    st.markdown(
        """
        <div class="iso-card">
            <div class="iso-row" style="margin-bottom:12px;">
                <div class="blk-title" style="margin:0;">📦 Catalog</div>
            </div>
        """,
        unsafe_allow_html=True
    )

    filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 1.4])
    filter_col1.selectbox("Category", ["All"] + list(CATEGORIES), key="cat_filter", label_visibility="collapsed")
    filter_col2.selectbox("Sort", ["Price: High", "Price: Low"], key="sort_filter", index=0, label_visibility="collapsed")
    filter_col3.text_input("Search", placeholder="Search items...", key="search_filter", label_visibility="collapsed")

    filtered_data = _filter_and_sort_packages(packages)
    if not filtered_data:
        st.info("No items found.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    cols = st.columns(3, gap="small")
    cart_ids = {str(item.get("_row_id")) for item in st.session_state["inv_items"]}

    for idx, row in enumerate(filtered_data):
        with cols[idx % 3]:
            is_main = row.get("category") == (CATEGORIES[0] if CATEGORIES else "Utama")
            bg_color, txt_color = ("#e8f5e9", "#15803d") if is_main else ("#fff7ed", "#c2410c")
            badge_text = "MAIN" if is_main else "ADD-ON"

            name = row.get("name", "Unnamed")
            price = safe_float(row.get("price"))

            desc_clean = normalize_desc_text(row.get("description", ""))
            lines = desc_to_lines(desc_clean)

            if lines:
                preview_text = "\n".join(lines[:2])
            else:
                preview, _, _ = _desc_meta(desc_clean, max_lines=2)
                preview_text = str(preview or "No details.").strip()

            preview_html = sanitize_text(preview_text).replace("\n", "<br/>")

            tooltip_html = ""
            if lines:
                full_desc = "".join([f"<div>• {sanitize_text(l)}</div>" for l in lines])
                tooltip_html = (
                    "<div class='tip'><b>📋 Details</b>"
                    f"<div style='margin-top:6px;'>{full_desc}</div></div>"
                )

            st.markdown(
                f"""
                <div class="card" style="border:1px solid #f3f4f6;">
                  <span class="pill" style="background:{bg_color}; color:{txt_color};">{badge_text}</span>
                  <div class="title">{sanitize_text(name)}</div>
                  <div class="price">{sanitize_text(rupiah(price))}</div>
                  <div class="desc">{preview_html}</div>
                  {tooltip_html}
                </div>
                """,
                unsafe_allow_html=True,
            )

            row_id = str(row.get("id", name))
            is_added = row_id in cart_ids
            st.button(
                "✓ Added" if is_added else "＋ Add",
                key=f"add_{row_id}_{idx}",
                disabled=is_added,
                use_container_width=True,
                on_click=cb_add_item_to_cart,
                args=(row,),
            )
            
    st.markdown("</div>", unsafe_allow_html=True)

def render_bundling_panel() -> None:
    # show bundling controls only if at least 2 non-bundle items exist
    non_bundle = _cart_non_bundle_items()
    bundles = _cart_bundle_items()

    if len(non_bundle) < 2 and not bundles:
        return

    # Collapsible Action Bar Style
    with st.expander("✨ Bundling Tools (Merge Items)", expanded=False):
        st.caption("Select items to merge into a single bundle line.")

        if len(non_bundle) < 2:
            st.info("Add at least 2 items to cart to enable bundling.")
        else:
            def _fmt_item_id(item_id: str) -> str:
                # display label for multiselect
                for it in non_bundle:
                    if str(it.get("__id")) == str(item_id):
                        nm = str(it.get("Description", "")).strip() or "Item"
                        pr = rupiah(safe_float(it.get("Price", 0)))
                        q = max(1, safe_int(it.get("Qty", 1), 1))
                        if q > 1:
                            return f"{nm} — {pr} × {q}"
                        return f"{nm} — {pr}"
                return str(item_id)

            options = [str(it.get("__id")) for it in non_bundle if str(it.get("__id"))]
            st.multiselect(
                "Select items to merge",
                options=options,
                key="bundle_sel",
                format_func=_fmt_item_id,
            )

            colA, colB = st.columns([1.3, 1])
            colA.text_input(
                "Bundle Title Override",
                key="bundle_title",
                placeholder="e.g. Full Package Bundle",
            )
            colB.selectbox(
                "Price Logic",
                ["Sum of selected", "Custom"],
                key="bundle_price_mode",
            )

            if st.session_state.get("bundle_price_mode") == "Custom":
                st.number_input(
                    "Custom Price",
                    min_value=0,
                    step=BUNDLE_PRICE_STEP,
                    key="bundle_custom_price",
                )

            st.button(
                "✨ Create Bundle",
                type="primary",
                use_container_width=True,
                on_click=cb_merge_selected_from_ui,
            )

        if bundles:
            st.divider()
            st.caption("Active Bundles")
            for b in bundles:
                bid = str(b.get("__id"))
                nm = str(b.get("Description", "Bundling"))
                st.write(f"• **{nm}** — {rupiah(safe_float(b.get('Price', 0)))}")
                st.button(
                    "↩️ Unmerge / Split",
                    key=f"unmerge_{bid}",
                    use_container_width=True,
                    on_click=cb_unmerge_bundle,
                    args=(bid,),
                )

def render_pos_section(subtotal: float, cashback: float, grand_total: float) -> None:
    # --- Bill Items Card ---
    st.markdown(
        """
        <div class="iso-card">
            <div class="iso-row" style="margin-bottom:12px;">
                <div class="blk-title" style="margin:0;">🛒 Bill Items</div>
            </div>
        """,
        unsafe_allow_html=True
    )

    # Bundling panel calls
    render_bundling_panel()

    st.markdown(
        "<div class='pos-head'>"
        "<div>Description</div>"
        "<div style='text-align:center;'>Qty</div>"
        "<div style='text-align:right;'>Total</div>"
        "<div></div>"
        "</div>",
        unsafe_allow_html=True,
    )

    items: List[Dict[str, Any]] = st.session_state["inv_items"]

    if not items:
        st.info("Cart is empty.")
    else:
        for idx, item in enumerate(items):
            item_id = item.get("__id", str(idx))
            is_bundle = bool(item.get("_bundle"))

            st.markdown("<div class='row'>", unsafe_allow_html=True)
            col1, col2, col3, col4 = st.columns(POS_COLUMN_RATIOS, gap="small", vertical_alignment="center")

            with col1:
                desc = sanitize_text(item.get('Description', ''))
                details = item.get('Details', '')
                st.markdown(
                    f"<div class='it'>{desc}</div>",
                    unsafe_allow_html=True,
                )
                # Show compact details if available
                if details:
                    details_preview = sanitize_text(details[:80]) + ('...' if len(details) > 80 else '')
                    st.markdown(
                        f"<div class='meta' style='margin-top:2px;'>{details_preview}</div>",
                        unsafe_allow_html=True,
                    )
                if is_bundle:
                    st.markdown("<div class='iso-badg badg-blue' style='margin-top:4px;'>BUNDLE</div>", unsafe_allow_html=True)
                    # Optional: Show bundle price input if mode is custom? 
                    # For simplicity, we stick to standard display unless user asks.
                    # If we want to allow editing, we check is_bundle logic.
                    if st.session_state.get("bundle_price_mode") == "Custom":
                         bp_key = f"bundle_price_{item_id}"
                         st.number_input(
                            "Price", min_value=0, step=BUNDLE_PRICE_STEP, key=bp_key, 
                            label_visibility="collapsed", on_change=cb_update_bundle_price, args=(item_id, bp_key)
                        )

            with col2:
                if is_bundle:
                    st.markdown("<div style='text-align:center;font-weight:bold;color:#6b7280;'>1</div>", unsafe_allow_html=True)
                else:
                    qty_key = f"qty_{item_id}"
                    st.number_input(
                        "Qty",
                        min_value=1,
                        step=1,
                        key=qty_key,
                        label_visibility="collapsed",
                        on_change=cb_update_item_qty,
                        args=(item_id, qty_key),
                    )

            with col3:
                st.markdown(f"<div class='tot'>{rupiah(safe_float(item.get('Total', 0)))}</div>", unsafe_allow_html=True)

            with col4:
                st.button(
                    "✕",
                    key=f"del_{item_id}",
                    on_click=cb_delete_item,
                    args=(item_id,),
                    type="secondary",
                    use_container_width=True,
                )

            st.markdown("</div>", unsafe_allow_html=True)

    # --- Totals ---
    st.markdown("<div style='margin-top:24px; border-top:1px dashed #e5e7eb; padding-top:16px;'></div>", unsafe_allow_html=True)
    
    t_c1, t_c2 = st.columns([1.5, 1])
    with t_c1:
        st.markdown("<div class='muted' style='margin-bottom:4px;'>Discount / Cashback</div>", unsafe_allow_html=True)
        st.number_input("Cashback", step=CASHBACK_STEP, key="inv_cashback", on_change=invalidate_pdf, label_visibility="collapsed")
    
    with t_c2:
        st.markdown(
            f"""
            <div class="grand" style="margin-top:0;">
              <div class="lbl">Grand Total</div>
              <div class="val">{rupiah(grand_total)}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
    st.markdown("</div>", unsafe_allow_html=True) # End Card


# ==============================================================================
# 7) EXPORT ACTIONS
# ==============================================================================

def generate_pdf_wrapper(subtotal: float, grand_total: float) -> None:
    try:
        meta = {
            "inv_no": st.session_state.get("inv_no", ""),
            "title": st.session_state.get("inv_title", "Invoice"),
            "date": datetime.now().strftime("%d %B %Y"),
            "client_name": st.session_state.get("inv_client_name", ""),
            "wedding_date": (st.session_state.get("inv_wedding_date") or date.today()).strftime("%d %B %Y"),
            "venue": st.session_state.get("inv_venue", ""),
            "subtotal": subtotal,
            "cashback": st.session_state.get("inv_cashback", 0),
            "pay_dp1": st.session_state.get("pay_dp1", 0),
            "pay_term2": st.session_state.get("pay_term2", 0),
            "pay_term3": st.session_state.get("pay_term3", 0),
            "pay_full": st.session_state.get("pay_full", 0),
            "terms": st.session_state.get("inv_terms", ""),
            "bank_name": st.session_state.get("bank_nm", ""),
            "bank_acc": st.session_state.get("bank_ac", ""),
            "bank_holder": st.session_state.get("bank_an", ""),
            "payment_proof": st.session_state.get("pp_cached") or []
        }

        with st.spinner("Generating PDF..."):
            pdf_bytes = invoice_mod.generate_pdf_bytes(meta, st.session_state["inv_items"], grand_total)

        if not pdf_bytes:
            raise ValueError("PDF Generator returned empty data.")

        st.session_state["generated_pdf_bytes"] = pdf_bytes
        st.toast("PDF Generated Successfully!", icon="✅")

    except Exception as e:
        st.session_state["generated_pdf_bytes"] = None
        st.error(f"Error generating PDF: {e}")

def render_download_section() -> None:
    pdf_data = st.session_state.get("generated_pdf_bytes")
    if not pdf_data:
        return

    # Normalize to bytes
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
    email_recipient = (st.session_state.get("inv_client_email") or "").strip()

    with st.container(border=True):
        st.markdown("<div class='blk-title'>✅ PDF Ready</div>", unsafe_allow_html=True)

        col1, col2 = st.columns(2, gap="small")

        col1.download_button(
            "📥 Download",
            data=pdf_bytes,
            file_name=file_name,
            mime="application/pdf",
            use_container_width=True,
        )

        # Shared Email (Maintenance Mode)
        col2.button(
            "☁️ Share (Maintenance)", 
            disabled=True, 
            use_container_width=True, 
            help="Fitur ini sedang dalam pemeliharaan (Maintenance up to date nanti)."
        )
        
        # if col2.button("☁️ Share Email", type="primary", use_container_width=True):
        #    # ... existing logic masked out ...

        # Save to History
        edit_id = st.session_state.get("editing_invoice_id")
        btn_label = f"💾 Update History (#{edit_id})" if edit_id else "💾 Save to History"
        
        if st.button(btn_label, use_container_width=True, on_click=_handle_save_history, args=(inv_no, email_recipient, pdf_bytes)):
             pass # Logic moved to callback

def _handle_save_history(inv_no: str, client_email: str, pdf_bytes: bytes) -> None:
    try:
        import json
        
        # 1. Gather Data
        meta = {
            "inv_no": st.session_state.get("inv_no", ""),
            "title": st.session_state.get("inv_title", ""),
            "date": datetime.now().strftime("%d %B %Y"),
            "client_name": st.session_state.get("inv_client_name", ""),
            "client_email": client_email,
            "wedding_date": (st.session_state.get("inv_wedding_date") or date.today()).strftime("%d %B %Y"),
            "venue": st.session_state.get("inv_venue", ""),
            "subtotal": 0,
            "cashback": safe_float(st.session_state.get("inv_cashback", 0)),
            "pay_dp1": safe_int(st.session_state.get("pay_dp1", 0)),
            "pay_term2": safe_int(st.session_state.get("pay_term2", 0)),
            "pay_term3": safe_int(st.session_state.get("pay_term3", 0)),
            "pay_full": safe_int(st.session_state.get("pay_full", 0)),
            "terms": st.session_state.get("inv_terms", ""),
            "bank_name": st.session_state.get("bank_nm", ""),
            "bank_acc": st.session_state.get("bank_ac", ""),
            "bank_holder": st.session_state.get("bank_an", ""),
            "payment_proof": st.session_state.get("pp_cached") or []
        }
        
        # Recalc Totals for DB
        items = st.session_state["inv_items"]
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
                json.dumps(payload)
            )
            st.toast("Updated! Redirecting to History...", icon="✅")
            st.session_state["editing_invoice_id"] = None
            
            # Redirect to History View
            st.session_state["menu_selection"] = "📜 Invoice History"
            if "nav_key" in st.session_state:
                st.session_state["nav_key"] += 1
            
        else:
            db.save_invoice(
                inv_no, 
                meta["client_name"], 
                date.today().strftime("%Y-%m-%d"), 
                grand, 
                json.dumps(payload)
            )
            st.toast("Invoice saved! Resetting form...", icon="💾")
            # Reset form for next input
            cb_reset_transaction()
        
        # Delay to show toast
        import time
        time.sleep(1.0)
            
    except Exception as e:
        st.error(f"Failed to save/update history: {e}")


# ==============================================================================
# 8) MAIN EXECUTION
# ==============================================================================

def render_page() -> None:
    initialize_session_state()
    inject_styles()

    page_header("🧾 Event Invoice Builder", "Manage sales, split payments, and generate invoices.")

    # Fetch catalog (cached)
    try:
        packages = load_packages_cached()
    except Exception as e:
        st.error(f"Connection Error: {e}")
        packages = []

    subtotal, grand_total = calculate_totals(
        st.session_state["inv_items"],
        safe_float(st.session_state.get("inv_cashback", 0)),
    )

    render_event_metadata()
    st.write("")

    # Layout: Catalog Top (Full), Bottom Split (Bill | Payment)
    
    # 1. Catalog (Full Width)
    render_catalog_section(packages)
    
    st.write("")
    st.divider()
    st.write("")
    
    # 2. Split: Bill (Left) | Payment (Right)
    bot_left, bot_right = st.columns([1.7, 1], gap="large")
    
    with bot_left:
        # Bill / POS Section
        render_pos_section(subtotal, safe_float(st.session_state.get("inv_cashback", 0)), grand_total)
        
    with bot_right:
        # Payment Schedule & Actions
        render_payment_section(grand_total)
