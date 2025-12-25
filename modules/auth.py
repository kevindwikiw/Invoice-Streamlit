# modules/auth.py
import time
import hmac
import base64
import hashlib
import secrets

import streamlit as st
import extra_streamlit_components as stx


# =========================================================
# 0) SECRETS
# =========================================================
def _get_auth_secrets():
    a = st.secrets.get("auth", {})
    return {
        "username": a.get("username", "admin"),
        "password_hash": a.get("password_hash", ""),
        "cookie_secret": a.get("cookie_secret", ""),
        "cookie_days": int(a.get("cookie_days", 14)),
    }


# =========================================================
# 1) COOKIE MANAGER (cached)
# =========================================================
@st.cache_resource
def get_manager():
    # Key harus statis string, jangan pakai random
    return stx.CookieManager(key="system_auth_manager")

cookie_manager = get_manager()
COOKIE_NAME = "admin_token"


def _cookie_set(name: str, value: str, expires_at: int | None, key: str):
    """
    extra_streamlit_components CookieManager versi beda bisa beda param.
    Kita handle best-effort.
    """
    try:
        cookie_manager.set(name, value, expires_at=expires_at, key=key)
        return
    except TypeError:
        pass
    except Exception:
        pass

    try:
        cookie_manager.set(name, value, key=key)
    except Exception:
        pass


def _cookie_delete(name: str, key: str):
    """
    Delete best-effort, kalau gagal paksa expire.
    """
    try:
        cookie_manager.delete(name, key=key)
        return
    except Exception:
        pass

    # fallback: force expire
    _cookie_set(name, "", expires_at=int(time.time()) - 10, key=f"{key}_expire")


# =========================================================
# 2) PASSWORD HASH (PBKDF2-SHA256)
# Stored format:
#   pbkdf2_sha256$iterations$salt$hash_b64
# =========================================================
def _pbkdf2_hash(password: str, salt: str, iterations: int) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return base64.urlsafe_b64encode(dk).decode("utf-8").rstrip("=")


def verify_password(password: str, stored: str) -> bool:
    try:
        alg, iters, salt, h = stored.split("$", 3)
        if alg != "pbkdf2_sha256":
            return False
        iters = int(iters)
        calc = _pbkdf2_hash(password, salt, iters)
        return hmac.compare_digest(calc, h)
    except Exception:
        return False


# Optional helper (kalau suatu saat mau generate hash via python)
def generate_password_hash(password: str, iterations: int = 260000) -> str:
    salt = secrets.token_urlsafe(16)
    h = _pbkdf2_hash(password, salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt}${h}"


# =========================================================
# 3) SIGNED COOKIE TOKEN (HMAC)
# token format: v1|username|exp_epoch|nonce|sig
# =========================================================
def _sign(msg: str, secret_key: str) -> str:
    sig = hmac.new(secret_key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode("utf-8").rstrip("=")


def _make_token(username: str, secret_key: str, ttl_seconds: int) -> str:
    exp = int(time.time()) + ttl_seconds
    nonce = secrets.token_urlsafe(12)
    msg = f"v1|{username}|{exp}|{nonce}"
    sig = _sign(msg, secret_key)
    return f"{msg}|{sig}"


def _verify_token(token: str, secret_key: str) -> str | None:
    try:
        parts = token.split("|")
        if len(parts) != 5:
            return None

        ver, username, exp_s, nonce, sig = parts
        if ver != "v1":
            return None

        exp = int(exp_s)
        if time.time() > exp:
            return None

        msg = f"{ver}|{username}|{exp_s}|{nonce}"
        expected = _sign(msg, secret_key)
        if not hmac.compare_digest(expected, sig):
            return None

        return username
    except Exception:
        return None


def boot_gate():
    # 1. Kalau di RAM sudah login, aman
    if st.session_state.get("logged_in", False):
        return

    # 2. Init counter
    if "_boot_gate_rerun_count" not in st.session_state:
        st.session_state["_boot_gate_rerun_count"] = 0

    # 3. Baca Cookie
    cookies = cookie_manager.get_all()

    # 4. LOGIKA SABAR:
    # Jika cookie kosong, kita akan coba refresh SAMPAI 2 KALI.
    # Refresh 1: Membangun jembatan Python <-> Browser
    # Refresh 2: Mengambil data
    if (not cookies) and st.session_state["_boot_gate_rerun_count"] < 2:
        st.session_state["_boot_gate_rerun_count"] += 1
        time.sleep(0.5) # Tunggu setengah detik
        st.rerun()

# =========================================================
# 5) LOGIN CHECK (FAST)
# =========================================================
def check_login() -> bool:

    # KODE LAMA KAMU:
    if st.session_state.pop("_skip_cookie_once", False):
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        return False

    if st.session_state.get("logged_in", False):
        return True

    sec = _get_auth_secrets()
    secret_key = sec["cookie_secret"]

    if not secret_key:
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        return False

    try:
        # Tambahkan 'or {}' untuk handle jika get_all return None
        cookies = cookie_manager.get_all() or {} 
        token = cookies.get("admin_token", "")
        username = _verify_token(token, secret_key) if token else None
        
        if username:
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            return True
    except Exception:
        pass

    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    return False


# =========================================================
# 6) UI LOGIN PAGE
# =========================================================
def login_page():
    sec = _get_auth_secrets()
    required_user = sec["username"]
    stored_hash = sec["password_hash"]
    secret_key = sec["cookie_secret"]
    cookie_days = sec["cookie_days"]

    if not stored_hash or not secret_key:
        st.error("Auth belum dikonfigurasi. Lengkapi .streamlit/secrets.toml")
        st.stop()

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔐 Akses Masuk</h2>", unsafe_allow_html=True)

        with st.container(border=True):
            st.session_state.setdefault("_login_fail", 0)

            with st.form("login_form"):
                st.write("Silakan masukkan akun Anda:")
                username = st.text_input("👤 Username")
                password = st.text_input("🔑 Password", type="password")

                submit = st.form_submit_button("Masuk Sistem", type="primary", use_container_width=True)

                if submit:
                    # slow-down ringan setelah beberapa gagal
                    if st.session_state["_login_fail"] >= 3:
                        time.sleep(0.4)

                    ok_user = (username.strip() == required_user)
                    ok_pass = verify_password(password, stored_hash)

                    if ok_user and ok_pass:
                        st.session_state["logged_in"] = True
                        st.session_state["username"] = username.strip()
                        st.session_state["_login_fail"] = 0

                        ttl = int(cookie_days) * 24 * 60 * 60
                        token = _make_token(username.strip(), secret_key, ttl_seconds=ttl)
                        expires_at = int(time.time()) + ttl

                        _cookie_set("admin_token", token, expires_at=expires_at, key="set_login_cookie")

                        st.toast("Login Berhasil!", icon="✅")
                        st.rerun()
                    else:
                        st.session_state["_login_fail"] += 1
                        st.error("Username atau Password salah!")


# =========================================================
# 7) LOGOUT CONFIRMATION
# =========================================================
@st.dialog(" ")
def show_logout_confirmation():
    st.markdown(
        """
        <div style="text-align:center; padding: 10px;">
            <div style="font-size: 44px; margin-bottom: 10px;">👋</div>
            <div style="font-size: 18px; font-weight: 800; margin-bottom: 6px; color: #1a1a1a;">Konfirmasi Logout</div>
            <div style="font-size: 14px; color: #6e6e73; margin-bottom: 18px;">Apakah Anda yakin ingin keluar dari sistem?</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)

    with c1:
        if st.button("Batal", use_container_width=True):
            st.rerun()

    with c2:
        if st.button("Ya, Keluar", type="primary", use_container_width=True):
            # expire cookie (lebih reliable)
            _cookie_delete("admin_token", key="logout_cookie")

            # clear session auth
            st.session_state["logged_in"] = False
            st.session_state["username"] = ""
            st.session_state["_skip_cookie_once"] = True

            # supaya next reload gak rerun-loop
            st.session_state["_boot_gate_done"] = True
            st.session_state["_boot_gate_rerun_count"] = 1

            st.rerun()


# =========================================================
# 8) LOGOUT BUTTON
# =========================================================
def logout_button():
    if st.sidebar.button("🚪 Logout", key="sidebar_logout_btn", use_container_width=True):
        show_logout_confirmation()
