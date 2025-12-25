# modules/auth.py
import time
import hmac
import base64
import hashlib
import secrets
import os
from datetime import datetime, timedelta
import streamlit as st
import extra_streamlit_components as stx

# Internal UI components
try:
    from ui.components import danger_container
except ImportError:
    danger_container = None

# =========================================================
# A. CONFIGURATION
# =========================================================
def _get_secrets():
    """Fetching secrets from st.secrets (local) or Environment Variables (Fly.io)."""
    def get_val(key, default=None):
        # Prioritas: 1. st.secrets, 2. OS Environment
        try:
            if key in st.secrets: return st.secrets[key]
        except: pass
        return os.environ.get(key, default)

    return {
        "user": get_val("AUTH_USERNAME", "admin"),
        "hash": get_val("AUTH_PASSWORD_HASH", ""),
        "key": get_val("AUTH_COOKIE_SECRET", ""),
        "days": int(get_val("AUTH_COOKIE_DAYS", 14)),
        "token_name": get_val("AUTH_COOKIE_NAME", "admin_auth_token"),
        "boot_wait": float(get_val("AUTH_COOKIE_BOOT_WAIT", 2.5)),
        "boot_sleep": float(get_val("AUTH_COOKIE_BOOT_SLEEP", 0.12)),
        "idle_timeout_min": int(get_val("AUTH_IDLE_TIMEOUT_MIN", 30)),
    }

@st.cache_resource
def get_cookie_manager():
    return stx.CookieManager(key="prod_auth_manager_v2")

cookie_manager = get_cookie_manager()

# =========================================================
# B. CRYPTO UTILS
# =========================================================
def _hash_pw(password: str, salt: str, iters: int) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iters)
    return base64.urlsafe_b64encode(dk).decode().rstrip("=")

def _verify_pw(password: str, stored: str) -> bool:
    try:
        if not stored or "$" not in stored: return False
        _, iters, salt, h = stored.split("$", 3)
        return hmac.compare_digest(_hash_pw(password, salt, int(iters)), h)
    except: return False

def _create_token(user: str, key: str, days: int) -> str:
    exp = int(time.time()) + (days * 86400)
    msg = f"v1|{user}|{exp}|{secrets.token_urlsafe(16)}"
    sig = hmac.new(key.encode(), msg.encode(), hashlib.sha256).digest()
    return f"{msg}|{base64.urlsafe_b64encode(sig).decode().rstrip('=')}"

def _validate_token(token: str, key: str) -> str | None:
    try:
        ver, user, exp_s, nonce, sig = token.split("|")
        if ver != "v1" or int(exp_s) < int(time.time()): return None
        expected = hmac.new(key.encode(), f"{ver}|{user}|{exp_s}|{nonce}".encode(), hashlib.sha256).digest()
        actual = base64.urlsafe_b64encode(expected).decode().rstrip('=')
        return user if hmac.compare_digest(actual, sig) else None
    except: return None

# =========================================================
# C. PERSISTENCE & IDLE ENGINE
# =========================================================
def check_login() -> bool:
    """The absolute guard. Handles RAM cache, Browser Cookie, and Idle Timeout."""
    if st.session_state.get("_force_logout", False):
        return False

    conf = _get_secrets()

    # 1. Check Idle Timeout for active sessions
    if st.session_state.get("logged_in"):
        last_active = st.session_state.get("_last_active_at", 0)
        if last_active > 0:
            elapsed_min = (time.time() - last_active) / 60
            if elapsed_min > conf["idle_timeout_min"]:
                _exec_logout(reason="Session expired due to inactivity. 🕒")
                return False
        
        # Update activity timestamp on every interaction
        st.session_state["_last_active_at"] = time.time()
        return True

    # 2. Config guard
    if not conf["key"]:
        st.error("🚨 Critical: AUTH_COOKIE_SECRET is not configured.")
        return False

    # 3. Cookie Hydration Gate
    if "_boot_time" not in st.session_state:
        st.session_state["_boot_time"] = time.time()

    cookies = cookie_manager.get_all()
    if not cookies:
        elapsed = time.time() - st.session_state["_boot_time"]
        if elapsed < conf["boot_wait"]:
            time.sleep(conf["boot_sleep"])
            st.rerun()
        return False

    # 4. Token validation from Cookie
    token = cookies.get(conf["token_name"])
    if token:
        user = _validate_token(token, conf["key"])
        if user:
            st.session_state["logged_in"] = True
            st.session_state["username"] = user
            st.session_state["_last_active_at"] = time.time()
            return True
            
    return False

def _exec_logout(reason: str = None):
    """Unified atomic logout execution."""
    conf = _get_secrets()
    st.session_state["_force_logout"] = True
    cookie_manager.delete(conf["token_name"], key=f"logout_{int(time.time())}")
    
    # Selective cleanup
    for k in ["logged_in", "username", "_boot_time", "_last_active_at"]:
        st.session_state.pop(k, None)
    
    if reason:
        st.toast(reason, icon="🔒")
        time.sleep(1)
    st.rerun()

# =========================================================
# D. UI COMPONENTS
# =========================================================
def login_page():
    conf = _get_secrets()
    st.session_state["_force_logout"] = False 

    st.markdown("""<style>
        [data-testid="stHeader"], [data-testid="stSidebar"] {visibility: hidden;}
        .block-container {padding-top: 5rem;}
    </style>""", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        st.markdown("<div style='text-align:center; font-size:54px;'>🛸</div>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center; margin-bottom:.25rem;'>Admin Portal</h2>", unsafe_allow_html=True)
        
        with st.container(border=True):
            with st.form("login_form"):
                u = st.text_input("👤 Username", placeholder="e.g. admin")
                p = st.text_input("🔑 Password", type="password", placeholder="••••••••")
                if st.form_submit_button("✨ Sign In", type="primary", use_container_width=True):
                    if u == conf["user"] and _verify_pw(p, conf["hash"]):
                        st.session_state["logged_in"] = True
                        st.session_state["username"] = u
                        st.session_state["_last_active_at"] = time.time()
                        
                        token = _create_token(u, conf["key"], conf["days"])
                        exp = datetime.now() + timedelta(days=conf["days"])
                        cookie_manager.set(conf["token_name"], token, expires_at=exp, key=f"login_{int(time.time())}")
                        
                        st.success("Authorized! Redirecting...")
                        time.sleep(0.8)
                        st.rerun()
                    else:
                        st.error("❌ Invalid credentials.")

@st.dialog("🚪 Sign Out")
def show_logout_dialog():
    st.write("Are you sure you want to end your session?")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", use_container_width=True):
        st.rerun()
    
    with c2:
        if danger_container:
            with danger_container(key="logout_danger"):
                if st.button("Yes, Logout", type="primary", use_container_width=True):
                    _exec_logout()
        else:
            if st.button("Yes, Logout", type="primary", use_container_width=True):
                _exec_logout()

def logout_button():
    if st.sidebar.button("🚪 Sign Out", use_container_width=True):
        show_logout_dialog()

