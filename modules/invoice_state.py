import streamlit as st
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from modules import db
from modules.utils import normalize_db_records

# --- Constants ---
DEFAULT_INVOICE_TITLE = "Wedding Invoice"
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
DEFAULT_FOOTER_ITEMS = (
    "Jl. Panembakan Gg Sukamaju 15 No. 3, Kota Cimahi\n"
    "theorbitphoto@gmail.com\n"
    "@theorbitphoto\n"
    "0813-2333-1506"
)

CATALOG_CACHE_TTL_SEC = 300

# --- State Helpers ---

def invalidate_pdf():
    """Invalidates the generated PDF so it is regenerated on next render."""
    st.session_state["generated_pdf_bytes"] = None

@st.cache_data(show_spinner=False, ttl=CATALOG_CACHE_TTL_SEC)
def load_db_settings() -> Dict[str, Any]:
    return {
        "title": db.get_config("inv_title_default", DEFAULT_INVOICE_TITLE),
        "terms": db.get_config("inv_terms_default", DEFAULT_TERMS),
        "bank_nm": db.get_config("bank_nm_default", DEFAULT_BANK_INFO["bank_nm"]),
        "bank_ac": db.get_config("bank_ac_default", DEFAULT_BANK_INFO["bank_ac"]),
        "bank_an": db.get_config("bank_an_default", DEFAULT_BANK_INFO["bank_an"]),
        "inv_footer": db.get_config("inv_footer_default", DEFAULT_FOOTER_ITEMS),
    }

@st.cache_data(show_spinner=False, ttl=CATALOG_CACHE_TTL_SEC)
def load_packages_cached(version_key: str) -> List[Dict[str, Any]]:
    # version_key is just for invalidation (not used in function)
    raw = db.load_packages()
    return normalize_db_records(raw)

@st.cache_data(show_spinner=False, ttl=10)  # Short TTL for dashboard stats (10s)
def get_dashboard_stats_cached() -> Dict[str, Any]:
    return db.get_dashboard_stats()

@st.cache_data(show_spinner=False, ttl=10)
def get_config_cached(key: str, default: Any = None) -> Any:
    return db.get_config(key, default)

def ensure_invoice_no_exists():
    """Guarantees that inv_no is populated in session state. Use fallback if DB fails."""
    if st.session_state.get("inv_no"):
        return

    try:
        # Optimized: Use cached config to avoid DB hit on every refresh
        current_seq_str = get_config_cached("inv_seq_global", "0")
        draft_seq = int(current_seq_str) + 1 if str(current_seq_str).isdigit() else 1
        
        st.session_state["_draft_global_seq"] = draft_seq
        
        # Format: INV{seq} (Padding 5 digits)
        new_no = f"INV{draft_seq:05d}"
        st.session_state["inv_no"] = new_no
        
    except Exception as e:
        # Debug logging visible to user
        st.toast(f"⚠️ Auto-gen failed: {e}. Using fallback.", icon="⚠️")
        
        # Professional Fallback: INV + Compact Timestamp
        # e.g. INV2601271401
        ts_suffix = datetime.now().strftime("%y%m%d%H%M") 
        st.session_state["inv_no"] = f"INV{ts_suffix}"

def initialize_session_state() -> None:
    # Load custom defaults from DB
    db_conf = load_db_settings()

    # Check for reset flags (set by cb_reset_transaction)
    def get_with_reset_flag(key: str, db_default: Any, fallback: Any = None) -> Any:
        flag_key = f"_default_{key}"
        if flag_key in st.session_state:
            val = st.session_state.pop(flag_key)
            return val
        return db_default if db_default is not None else fallback

    defaults: Dict[str, Any] = {
        # Cart Data
        "inv_items": [],
        "inv_cashback": 0,
        "generated_pdf_bytes": None,

        # Invoice Metadata
        "inv_title": "",
        # "inv_no": "",  # REMOVED from defaults, handled by ensure_invoice_no_exists
        "inv_client_name": "",
        "inv_client_phone": "",
        "inv_client_email": "",
        # Default date as string (e.g. "20 October 2026")
        "inv_wedding_date": (date.today() + timedelta(days=90)).strftime("%d %B %Y"),
        "inv_venue": "",

        # Payment Schedule - Dynamic terms (min 2: DP + Pelunasan)
        "payment_terms": [
            {"id": "dp", "label": "Down Payment", "amount": 0, "locked": True},
            {"id": "full", "label": "Pelunasan", "amount": 0, "locked": True},
        ],
        
        # Payment Proofs
        "pp_cached": [],
        
        # Configs
        "inv_terms": get_with_reset_flag("inv_terms", db_conf["terms"], DEFAULT_TERMS),
        "bank_nm": get_with_reset_flag("bank_nm", db_conf["bank_nm"], DEFAULT_BANK_INFO["bank_nm"]),
        "bank_ac": get_with_reset_flag("bank_ac", db_conf["bank_ac"], DEFAULT_BANK_INFO["bank_ac"]),
        "bank_an": get_with_reset_flag("bank_an", db_conf["bank_an"], DEFAULT_BANK_INFO["bank_an"]),
        "inv_footer": get_with_reset_flag("inv_footer", db_conf["inv_footer"], DEFAULT_FOOTER_ITEMS),
        
        # Flags
        "editing_invoice_id": None,
        "uploader_key": 0,
    }

    # Apply defaults if key missing
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
            
    # MIGRATION: Ensure inv_wedding_date is STRING (fix for legacy date objects in session)
    if "inv_wedding_date" in st.session_state:
        val = st.session_state["inv_wedding_date"]
        if not isinstance(val, str):
            # Convert date/datetime/other to string format or empty
            try:
                st.session_state["inv_wedding_date"] = val.strftime("%d %B %Y")
            except:
                 st.session_state["inv_wedding_date"] = ""
    
    # Ensure Invoice No Exists (Force Generation if empty)
    ensure_invoice_no_exists()
    # Double check emptiness (e.g. if key existed but was "")
    if not st.session_state.get("inv_no"):
         st.session_state.pop("inv_no", None) # Clear invalid empty string
         ensure_invoice_no_exists() # Retry

    # Ensure inv_items is a list
    if not isinstance(st.session_state["inv_items"], list):
        st.session_state["inv_items"] = []
    
    # Ensure payment_terms structure
    if "payment_terms" in st.session_state:
        pt = st.session_state["payment_terms"]
        if not pt or not isinstance(pt, list):
             st.session_state["payment_terms"] = defaults["payment_terms"]

# --- Invoice No Logic ---

def _sanitize_client_name(name: str) -> str:
    """Extract clean uppercase identifier from client name."""
    import re
    # Remove special chars, keep only letters/numbers
    clean = re.sub(r'[^a-zA-Z0-9]', '', name)
    # Take first 12 chars uppercase
    return clean[:12].upper() if clean else ""

# --- Versioning Helper Cached ---
@st.cache_data(show_spinner=False, ttl=10)
def get_package_version_cached() -> str:
    """Cached wrapper for DB package version to avoid connection overhead."""
    return db.get_package_version()

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
