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

# --- UI Components ---
from ui.components import page_header
from ui.formatters import rupiah

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
POS_COLUMN_RATIOS = [2.4, 0.6, 2, 0.7]  # Description | Qty | Total | Del
MIN_QTY = 1

CASHBACK_STEP = 500_000
PAYMENT_STEP = 1_000_000

DEFAULT_INVOICE_TITLE = "Exhibition Package 2026"
DEFAULT_TERMS = (
    "1. Down Payment sebesar Rp 500.000 (Lima Ratus Ribu Rupiah) saat di booth pameran\n"
    "2. Termin pembayaran H+7 Pameran: Rp 500.000, H-7 prewedding: Rp 3.000.000, dan pelunasan H-7 wedding\n"
    "3. Maksimal pembayaran Invoice 1 minggu dari tanggal invoice\n"
    "4. Paket yang telah dipilih tidak bisa down grade\n"
    "5. Melakukan pembayaran berarti menyatakan setuju dengan detail invoice. Pembayaran yang telah dilakukan tidak bisa di refund"
)
DEFAULT_BANK_INFO = {
    "bank_nm": "OCBC",
    "bank_ac": "693810505794",
    "bank_an": "FANI PUSPITA NINGRUM",
}

CATALOG_CACHE_TTL_SEC = 300  # 5 min, safe default


# ==============================================================================
# 2) STYLING (CSS)
# ==============================================================================

def _pos_grid_template(ratios: List[float]) -> str:
    return " ".join([f"{r}fr" for r in ratios])

def _get_custom_css() -> str:
    """Returns CSS styles for the invoice view."""
    grid = _pos_grid_template(POS_COLUMN_RATIOS)
    return f"""
    <style>
    /* --- UTILITIES --- */
    .hrow {{ display:flex; gap:10px; align-items:center; justify-content:space-between; }}
    .muted {{ color:#6b7280; font-size:.85rem; }}
    .pill {{ font-size:.72rem; font-weight:900; padding:2px 10px; border-radius:999px; display:inline-block; }}
    .statusbar {{
        display:flex; align-items:center; justify-content:space-between; gap:10px; padding:10px 12px;
        border-radius:12px; border:1px solid rgba(0,0,0,.06); background:#f9fafb;
    }}
    .status-title {{ font-weight:900; color:#111827; font-size:.85rem; letter-spacing:.01em; }}
    .status-right {{ display:flex; align-items:center; gap:8px; }}

    /* --- SECTION TITLES --- */
    .blk-title {{
        font-size:1.02rem; font-weight:900; color:#111827;
        line-height:1.2; margin:0 0 10px 0;
    }}
    .blk-sub {{ font-size:.82rem; color:#6b7280; margin-top:-6px; margin-bottom:10px; }}

    /* --- CATALOG CARD --- */
    .card {{
        background:#fff; border:1px solid #e5e7eb; border-radius:14px; padding:14px;
        transition:.15s ease; position:relative; height:100%, overflow: visible;;
    }}
    .card:hover {{ border-color:#cbd5e1; box-shadow:0 10px 22px rgba(0,0,0,.07); transform:translateY(-2px); }}
    .title {{ font-weight:900; font-size:.95rem; color:#111827; line-height:1.25; margin-top:6px; }}
    .price {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-weight:900; color:#2563eb; margin-top:2px; }}
    .desc {{
        font-size:.82rem; color:#6b7280; margin-top:6px; line-height:1.45;
        display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; min-height:36px;
    }}
    .tip {{
        display:none; position:absolute; left:0; right:0; bottom:100%;
        background:#fff; border:1px solid #e5e7eb; border-radius:14px; padding:12px;
        box-shadow:0 14px 30px rgba(0,0,0,.12); z-index:30; margin-bottom:10px; font-size:.82rem;
    }}
    .card:hover .tip {{ display:block; }}

    /* --- POS TABLE --- */
    .pos-head {{
        display:grid; grid-template-columns:{grid};
        gap:10px; align-items:center; font-size:.72rem; font-weight:900; color:#9ca3af;
        text-transform:uppercase; letter-spacing:.05em; padding:0 0 10px 0;
        border-bottom:1px solid #eee; margin-bottom:8px;
    }}
    .row {{ border-bottom:1px solid #f3f4f6; padding:10px 0; }}
    .it {{ font-weight:900; color:#111827; font-size:.92rem; line-height:1.25; }}
    .meta {{ font-size:.78rem; color:#9ca3af; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
    .tot {{ text-align:right; font-variant-numeric: tabular-nums; font-weight:950; color:#111827; font-size:1.02rem; }}

    /* --- GRAND TOTAL BOX --- */
    .grand {{
        background:#f9fafb; border:1px solid rgba(0,0,0,.06); border-radius:14px;
        padding:14px; text-align:right; margin-top:12px;
    }}
    .grand .lbl {{ font-size:.75rem; font-weight:900; color:#6b7280; text-transform:uppercase; letter-spacing:.05em; }}
    .grand .val {{ font-size:1.65rem; font-weight:950; color:#111827; margin-top:2px; }}

    /* --- WIDGET OVERRIDES --- */
    div[data-testid="stNumberInput"] {{ min-width:0!important; width:100%!important; }}
    div[data-testid="stNumberInput"] input {{ height:2.1rem!important; text-align:center; font-weight:800; padding:0 .25rem!important; }}
    div[data-testid="stButton"] button {{ padding:.28rem .55rem; min-height:0; }}
    </style>
    """

def inject_styles() -> None:
    st.markdown(_get_custom_css(), unsafe_allow_html=True)


# ==============================================================================
# 3) HELPERS (minimal, no extra imports)
# ==============================================================================

def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default

def normalize_db_records(raw_data: Any) -> List[Dict[str, Any]]:
    """Normalizes DB output into list[dict]. Supports DataFrame-like to_dict('records')."""
    if raw_data is None:
        return []
    if hasattr(raw_data, "to_dict"):
        try:
            return raw_data.to_dict("records")
        except Exception:
            return []
    if isinstance(raw_data, list):
        return raw_data
    return []

def calculate_totals(items: List[Dict[str, Any]], cashback: float) -> Tuple[float, float]:
    subtotal = sum(
        safe_float(item.get("Price", 0)) * max(MIN_QTY, safe_int(item.get("Qty", 1), 1))
        for item in items
    )
    grand_total = max(0.0, subtotal - max(0.0, cashback))
    return subtotal, grand_total

def sanitize_text(text: Any) -> str:
    """Tiny HTML escape w/o imports (safe for unsafe_allow_html)."""
    s = str(text or "")
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;").replace(">", "&gt;")
    s = s.replace('"', "&quot;").replace("'", "&#x27;")
    return s

def desc_to_lines(desc_clean: str) -> List[str]:
    """
    Turn normalized description into clean bullet lines.
    - split by newline
    - strip common bullet chars
    - drop empties
    """
    lines: List[str] = []
    for raw in (desc_clean or "").split("\n"):
        s = str(raw).strip()
        if not s:
            continue
        # trim bullet prefixes
        s = s.lstrip("-•·").strip()
        if s:
            lines.append(s)
    return lines

def normalize_desc_text(raw: Any) -> str:
    """
    Convert any <br ...> or &lt;br ...&gt; variants into newlines.
    No regex, no html import.
    """
    s = str(raw or "")

    # 1) Handle escaped: &lt;br ...&gt;
    # Convert to a temporary real tag then parse with the same logic.
    s = s.replace("&lt;", "<").replace("&gt;", ">")

    # 2) Replace any <br ...> (any case/spacing/attrs) with newline
    out = []
    i = 0
    n = len(s)
    while i < n:
        # case-insensitive check for "<br"
        if s[i] == "<" and i + 2 < n and s[i:i+3].lower() == "<br":
            j = i + 3
            # jump until closing '>' (if exists)
            while j < n and s[j] != ">":
                j += 1
            if j < n and s[j] == ">":
                out.append("\n")
                i = j + 1
                continue
        out.append(s[i])
        i += 1

    s = "".join(out)

    # Normalize line breaks + trim
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    return s.strip()

def is_valid_email(email: str) -> bool:
    """Minimal sanity check (no regex)."""
    e = (email or "").strip()
    if not e or " " in e or "@" not in e:
        return False
    local, domain = e.rsplit("@", 1)
    if not local or not domain or "." not in domain:
        return False
    if domain.startswith(".") or domain.endswith(".") or ".." in e:
        return False
    return True

def make_safe_filename(inv_no: str, prefix: str = "INV") -> str:
    inv_no = (inv_no or prefix).strip()
    safe_name = inv_no.replace("/", "_").replace("\\", "_").strip()
    return safe_name or "invoice"

def payment_integrity_status(
    grand_total: float,
    dp1: int,
    term2: int,
    term3: int,
    full: int,
) -> Tuple[str, str, int]:
    """
    Returns (status, message, balance)
    status: BALANCED | UNALLOCATED | OVER | INFO
    balance = grand_total - total_scheduled
    """
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
    defaults: Dict[str, Any] = {
        # Cart Data
        "inv_items": [],
        "inv_cashback": 0,
        "generated_pdf_bytes": None,

        # Invoice Metadata
        "inv_title": DEFAULT_INVOICE_TITLE,
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
        "inv_terms": DEFAULT_TERMS,
        "bank_nm": DEFAULT_BANK_INFO["bank_nm"],
        "bank_ac": DEFAULT_BANK_INFO["bank_ac"],
        "bank_an": DEFAULT_BANK_INFO["bank_an"],

        # UI Filters
        "cat_filter": "All",
        "sort_filter": "Price: High",
        "search_filter": "",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

def invalidate_pdf() -> None:
    st.session_state["generated_pdf_bytes"] = None

def _cleanup_qty_keys_for_item(item: Dict[str, Any]) -> None:
    item_id = item.get("__id")
    if not item_id:
        return
    qty_key = f"qty_{item_id}"
    if qty_key in st.session_state:
        del st.session_state[qty_key]

def cleanup_all_qty_keys() -> None:
    for k in list(st.session_state.keys()):
        if str(k).startswith("qty_"):
            del st.session_state[k]

def sync_qty_widget_state(items: List[Dict[str, Any]]) -> None:
    """
    Ensure widget state matches cart item Qty BEFORE widgets are instantiated.
    Prevents drift after resets/deletes.
    """
    for item in items:
        item_id = item.get("__id")
        if not item_id:
            continue
        qty_key = f"qty_{item_id}"
        desired = max(MIN_QTY, safe_int(item.get("Qty", 1), 1))
        st.session_state[qty_key] = desired


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

def cb_update_item_qty(item_index: int, widget_key: str) -> None:
    if not (0 <= item_index < len(st.session_state["inv_items"])):
        return

    raw_value = st.session_state.get(widget_key, 1)
    new_qty = max(MIN_QTY, safe_int(raw_value, 1))

    item = st.session_state["inv_items"][item_index]
    item["Qty"] = new_qty
    item["Total"] = safe_float(item.get("Price", 0)) * new_qty
    invalidate_pdf()

def cb_delete_item(item_index: int) -> None:
    if not (0 <= item_index < len(st.session_state["inv_items"])):
        return

    item = st.session_state["inv_items"][item_index]
    _cleanup_qty_keys_for_item(item)
    st.session_state["inv_items"].pop(item_index)
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
    st.session_state["pay_dp1"] = 0
    st.session_state["pay_term2"] = 0
    st.session_state["pay_term3"] = 0
    st.session_state["pay_full"] = 0
    cleanup_all_qty_keys()
    st.toast("Transaction cleared.", icon="🧹")


# ==============================================================================
# 6) UI RENDERERS
# ==============================================================================

def render_admin_panel(grand_total: float) -> None:
    with st.container(border=True):
        st.markdown("<div class='blk-title'>🧩 Admin Details</div>", unsafe_allow_html=True)
        st.markdown("<div class='blk-sub'>Invoice metadata + payment schedule.</div>", unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 1, 1])
        col1.text_input("Event / Title", key="inv_title", on_change=invalidate_pdf)
        col2.text_input("Invoice No", key="inv_no", on_change=invalidate_pdf)
        col3.date_input("Wedding Date", key="inv_wedding_date", on_change=invalidate_pdf)

        col4, col5, col6 = st.columns([1, 1, 1])
        col4.text_input("Client Name", key="inv_client_name", placeholder="CPW & CPP", on_change=invalidate_pdf)
        col5.text_input("Email", key="inv_client_email", placeholder="client@email.com", on_change=invalidate_pdf)
        col6.text_input("Venue", key="inv_venue", placeholder="Hotel/Gedung", on_change=invalidate_pdf)

        st.divider()
        st.markdown("<div class='blk-title'>💸 Payment Schedule</div>", unsafe_allow_html=True)

        dp1 = safe_int(st.session_state.get("pay_dp1", 0), 0)
        t2 = safe_int(st.session_state.get("pay_term2", 0), 0)
        t3 = safe_int(st.session_state.get("pay_term3", 0), 0)
        full = safe_int(st.session_state.get("pay_full", 0), 0)

        status, msg, _ = payment_integrity_status(grand_total, dp1, t2, t3, full)

        if status == "BALANCED":
            pill = "<span class='pill' style='background:#e8f5e9;color:#15803d;'>BALANCED</span>"
        elif status == "UNALLOCATED":
            pill = "<span class='pill' style='background:#fff7ed;color:#c2410c;'>UNALLOCATED</span>"
        elif status == "OVER":
            pill = "<span class='pill' style='background:#fee2e2;color:#b91c1c;'>OVER</span>"
        else:
            pill = "<span class='pill' style='background:#eef2ff;color:#3730a3;'>INFO</span>"

        st.markdown(
            f"""
            <div class="statusbar">
              <div>
                <div class="status-title">Payment Integrity</div>
                <div class="muted">{sanitize_text(msg)}</div>
              </div>
              <div class="status-right">{pill}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.write("")

        row1, row2, row3, row4 = st.columns(4)
        row1.number_input("DP 1", step=PAYMENT_STEP, key="pay_dp1", on_change=invalidate_pdf)
        row2.number_input("Term 2", step=PAYMENT_STEP, key="pay_term2", on_change=invalidate_pdf)
        row3.number_input("Term 3", step=PAYMENT_STEP, key="pay_term3", on_change=invalidate_pdf)
        row4.number_input("Pelunasan", step=PAYMENT_STEP, key="pay_full", on_change=invalidate_pdf)

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

        with st.expander("🏦 Bank & Terms Config", expanded=False):
            b_col1, b_col2, b_col3 = st.columns(3)
            b_col1.text_input("Bank Name", key="bank_nm", on_change=invalidate_pdf)
            b_col2.text_input("Account No", key="bank_ac", on_change=invalidate_pdf)
            b_col3.text_input("Account Holder", key="bank_an", on_change=invalidate_pdf)
            st.text_area("Terms & Conditions", key="inv_terms", height=110, on_change=invalidate_pdf)

def _filter_and_sort_packages(packages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cat_filter = st.session_state.get("cat_filter", "All")
    sort_filter = st.session_state.get("sort_filter", "Price: Highest")
    search_query = (st.session_state.get("search_filter", "") or "").lower().strip()

    filtered = list(packages)

    if cat_filter != "All":
        filtered = [p for p in filtered if p.get("category") == cat_filter]

    if search_query:
        filtered = [p for p in filtered if search_query in str(p.get("name", "")).lower()]

    if sort_filter == "Price: Low":
        filtered.sort(key=lambda x: safe_float(x.get("price")))
    else:
        # default Price: High
        filtered.sort(key=lambda x: safe_float(x.get("price")), reverse=True)

    return filtered

def render_catalog_section(packages: List[Dict[str, Any]]) -> None:
    with st.container(border=True):
        st.markdown("<div class='blk-title'>📦 Catalog</div>", unsafe_allow_html=True)

        filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 1.4])
        filter_col1.selectbox("Category", ["All"] + list(CATEGORIES), key="cat_filter", label_visibility="collapsed")
        filter_col2.selectbox("Sort", ["Price: High", "Price: Low"], key="sort_filter", index=0, label_visibility="collapsed")
        filter_col3.text_input("Search", placeholder="Search items...", key="search_filter", label_visibility="collapsed")

        filtered_data = _filter_and_sort_packages(packages)
        if not filtered_data:
            st.info("No items found.")
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

                # FIX: normalize <br> so it won't show literal in catalog
                desc_clean = normalize_desc_text(row.get("description", ""))
                lines = desc_to_lines(desc_clean)
                
                # preview 2 baris: pakai hasil parsing kita dulu (paling reliable)
                if lines:
                    preview_text = "\n".join(lines[:2])
                else:
                    # fallback: kalau desc kosong banget, baru pakai _desc_meta preview
                    preview, _, _ = _desc_meta(desc_clean, max_lines=2)
                    preview_text = str(preview or "No details.").strip()

                preview_html = sanitize_text(preview_text).replace("\n", "<br/>")
                
                tooltip_html = ""
                if lines:
                    # kalau cuma 1-2 baris, tooltip tetap boleh tampil (consistency)
                    full_desc = "".join([f"<div>• {sanitize_text(l)}</div>" for l in lines])
                    tooltip_html = (
                        "<div class='tip'><b>📋 Details</b>"
                        f"<div style='margin-top:6px;'>{full_desc}</div></div>"
                    )    

                # escape, tapi newline kita ubah jadi <br/> supaya keliatan enter di card
                preview_html = sanitize_text(preview_text).replace("\n", "<br/>")
                tooltip_html = ""
                if lines:
                    # kalau cuma 1-2 baris, tooltip tetap boleh tampil (consistency)
                    full_desc = "".join([f"<div>• {sanitize_text(l)}</div>" for l in lines])
                    tooltip_html = (
                        "<div class='tip'><b>📋 Details</b>"
                        f"<div style='margin-top:6px;'>{full_desc}</div></div>"
                    )
                    
                st.markdown(
                    f"""
                    <div class="card">
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

def render_pos_section(subtotal: float, cashback: float, grand_total: float) -> None:
    with st.container(border=True):
        st.markdown("<div class='blk-title'>🧾 POS</div>", unsafe_allow_html=True)

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
            sync_qty_widget_state(items)

            for idx, item in enumerate(items):
                item_id = item.get("__id", str(idx))

                st.markdown("<div class='row'>", unsafe_allow_html=True)
                col1, col2, col3, col4 = st.columns(POS_COLUMN_RATIOS, gap="small", vertical_alignment="center")

                with col1:
                    st.markdown(f"<div class='it'>{sanitize_text(item.get('Description', ''))}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='meta'>@ {sanitize_text(rupiah(safe_float(item.get('Price'))))}</div>", unsafe_allow_html=True)

                with col2:
                    qty_key = f"qty_{item_id}"
                    st.number_input(
                        "Qty",
                        min_value=MIN_QTY,
                        step=1,
                        key=qty_key,
                        label_visibility="collapsed",
                        on_change=cb_update_item_qty,
                        args=(idx, qty_key),
                    )

                with col3:
                    st.markdown(
                        f"<div class='tot'>{sanitize_text(rupiah(safe_float(item.get('Total'))))}</div>",
                        unsafe_allow_html=True,
                    )

                with col4:
                    st.button(
                        "✕",
                        key=f"del_{item_id}",
                        on_click=cb_delete_item,
                        args=(idx,),
                        use_container_width=True,
                    )

                st.markdown("</div>", unsafe_allow_html=True)

        st.divider()

        # Cashback: ONLY input (no +/- buttons)
        st.markdown("<div class='muted'><b>Discount / Cashback</b></div>", unsafe_allow_html=True)
        st.number_input(
            "Cashback",
            min_value=0,
            step=CASHBACK_STEP,
            key="inv_cashback",
            on_change=invalidate_pdf,
        )

        st.markdown(
            f"""
            <div class="grand">
              <div class="lbl">Grand Total</div>
              <div class="val">{sanitize_text(rupiah(grand_total))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.write("")

        act_col1, act_col2 = st.columns([1, 2], vertical_alignment="bottom")
        act_col1.button("Reset", on_click=cb_reset_transaction, use_container_width=True)

        is_valid_order = (len(items) > 0) and (grand_total > 0)
        already_ready = bool(st.session_state.get("generated_pdf_bytes"))
        btn_label = "✅ PDF Ready" if already_ready else "🚀 Process PDF"

        if act_col2.button(btn_label, type="primary", use_container_width=True, disabled=not is_valid_order):
            if already_ready:
                st.toast("PDF already generated (no changes detected).", icon="✅")
            else:
                generate_pdf_wrapper(subtotal, grand_total)


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

        if col2.button("☁️ Share Email", type="primary", use_container_width=True):
            if not is_valid_email(email_recipient):
                st.error("Please enter a valid email address.")
                return

            try:
                with st.spinner("Uploading to Google Drive & sharing..."):
                    pdf_stream = io.BytesIO(pdf_bytes)
                    success, link, msg = gdrive.upload_and_share(pdf_stream, file_name, email_recipient)

                if success:
                    st.success("Sent!")
                    if link:
                        st.link_button("Open Drive", link)
                else:
                    st.error(msg or "Upload failed.")
            except Exception as e:
                st.error(f"System Error: {e}")


# ==============================================================================
# 8) MAIN EXECUTION
# ==============================================================================

def render_page() -> None:
    initialize_session_state()
    inject_styles()

    page_header("Event Invoice Builder", "Manage sales, split payments, and generate invoices.")

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

    render_admin_panel(grand_total)
    st.write("")

    left_col, right_col = st.columns([1.7, 1], gap="large")
    with left_col:
        render_catalog_section(packages)
    with right_col:
        render_pos_section(subtotal, safe_float(st.session_state.get("inv_cashback", 0)), grand_total)
        render_download_section()
