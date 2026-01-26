# modules/auth.py
import os
import time
import hmac
import base64
import hashlib
import secrets
import urllib.parse
from datetime import datetime, timedelta

import streamlit as st
import streamlit.components.v1 as components

# Optional UI component (your custom danger container)
try:
    from views.styles import danger_container
except Exception:
    danger_container = None


# =========================================================
# A. CONFIGURATION
# =========================================================
def _get_secrets() -> dict:
    """Fetch secrets from OS env (Fly.io) or st.secrets (local)."""

    def safe_get(key: str):
        val = os.environ.get(key)
        if val:
            return val
        try:
            if key in st.secrets:
                return st.secrets[key]
        except Exception:
            pass
        return None

    return {
        "user": safe_get("AUTH_USERNAME") or "admin",
        "hash": safe_get("AUTH_PASSWORD_HASH") or "",
        "key": safe_get("AUTH_COOKIE_SECRET") or "",
        "days": int(safe_get("AUTH_COOKIE_DAYS") or 14),
        "token_name": safe_get("AUTH_COOKIE_NAME") or "admin_auth_token",
        "idle_timeout_min": int(safe_get("AUTH_IDLE_TIMEOUT_MIN") or 30),
        "superadmin_user": safe_get("SUPERADMIN_USERNAME") or "",
        "superadmin_hash": safe_get("SUPERADMIN_HASH") or "",
    }


# =========================================================
# B. DB SAFE WRAPPERS (NO CRASH)
# =========================================================
def _db_get(key: str) -> str | None:
    """Safe DB getter: returns None on error."""
    try:
        from modules import db

        v = db.get_config(key)
        return v if v else None
    except Exception as e:
        print(f"[AUTH DB ERROR] Read failed for {key}: {e}")
        return None


def _db_set(key: str, value: str) -> bool:
    """Safe DB setter: returns False on error."""
    try:
        from modules import db

        db.set_config(key, value)
        return True
    except Exception as e:
        print(f"[AUTH DB ERROR] Write failed for {key}: {e}")
        return False


# =========================================================
# C. CRYPTO UTILS
# =========================================================
def _hash_pw(password: str, salt: str, iters: int) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iters)
    return base64.urlsafe_b64encode(dk).decode().rstrip("=")


def _verify_pw(password: str, stored: str) -> bool:
    try:
        if not stored or "$" not in stored:
            return False
        _, iters, salt, h = stored.split("$", 3)
        return hmac.compare_digest(_hash_pw(password, salt, int(iters)), h)
    except Exception:
        return False


def generate_password_hash(password: str, iters: int = 100000) -> str:
    """Generate a password hash for storage."""
    salt = secrets.token_urlsafe(16)
    h = _hash_pw(password, salt, iters)
    return f"pbkdf2${iters}${salt}${h}"


def _create_token(user: str, key: str, days: int) -> str:
    """
    Token format:
    v1|user|exp|nonce|sig
    """
    exp = int(time.time()) + (days * 86400)
    msg = f"v1|{user}|{exp}|{secrets.token_urlsafe(16)}"
    sig = hmac.new(key.encode(), msg.encode(), hashlib.sha256).digest()
    return f"{msg}|{base64.urlsafe_b64encode(sig).decode().rstrip('=')}"


def _validate_token(token: str, key: str) -> tuple[str, str] | None:
    """
    Validate token signature + expiry.
    Returns (user, session_id/nonce) if valid, else None.
    """
    try:
        ver, user, exp_s, nonce, sig = token.split("|")
        if ver != "v1":
            print(f"[AUTH-VALIDATE] Fail: version {ver} != v1")
            return None

        now_ts = int(time.time())
        exp_ts = int(exp_s)
        if exp_ts < now_ts:
            print(f"[AUTH-VALIDATE] Fail: expired. exp={exp_ts}, now={now_ts}")
            return None

        msg = f"{ver}|{user}|{exp_s}|{nonce}"
        expected = hmac.new(key.encode(), msg.encode(), hashlib.sha256).digest()
        expected_sig = base64.urlsafe_b64encode(expected).decode().rstrip("=")

        if hmac.compare_digest(expected_sig, sig):
            return user, nonce

        print(f"[AUTH-VALIDATE] Fail: Sig mismatch.")
        return None
    except Exception as e:
        print(f"[AUTH-VALIDATE] Exception: {e}")
        return None


# =========================================================
# D. PASSWORD SOURCE (DB FIRST)
# =========================================================
def _get_db_password_hash(username: str) -> str | None:
    return _db_get(f"user_password_{username}")


def _set_db_password_hash(username: str, password_hash: str) -> bool:
    return _db_set(f"user_password_{username}", password_hash)


def verify_user_password(username: str, password: str) -> bool:
    """
    Security Logic:
    - If user has DB password → ONLY accept DB password (secrets disabled)
    - If user has NO DB password → Allow secrets (first-time/fallback)
    - Superadmin always has emergency fallback via secrets
    """
    conf = _get_secrets()

    # 1) DB password
    db_hash = _get_db_password_hash(username)
    if db_hash:
        return _verify_pw(password, db_hash)

    # 2) fallback admin secrets
    if username == conf["user"] and _verify_pw(password, conf["hash"]):
        return True

    # 3) superadmin secrets fallback
    if username == conf["superadmin_user"] and _verify_pw(password, conf["superadmin_hash"]):
        return True

    return False


# =========================================================
# E. BLACKLIST ENGINE (SESSION_ID / NONCE)
# =========================================================
BLACKLIST_KEY = "blacklisted_sessions"
BLACKLIST_KEEP = 30


def _get_blacklist_list() -> list[str]:
    raw = _db_get(BLACKLIST_KEY)
    if not raw:
        return []
    return [x for x in raw.split("|") if x]


def _is_session_blacklisted(session_id: str) -> bool:
    if not session_id:
        return False
    items = set(_get_blacklist_list())
    return session_id in items


def _blacklist_session(session_id: str) -> None:
    """Dedup + append, keep last N."""
    if not session_id:
        return
    items = _get_blacklist_list()
    items = [x for x in items if x != session_id]  # dedup
    items.append(session_id)
    items = items[-BLACKLIST_KEEP:]
    _db_set(BLACKLIST_KEY, "|".join(items))


# =========================================================
# F. COOKIE HELPERS (RELIABLE FOR STREAMLIT)
# =========================================================
def _cookie_js(name: str, value: str, days: int, reload: bool = False):
    """
    Reliable cookie setter for Streamlit:
    - Uses components.html (NOT st.html)
    - Writes cookie on window.top.document (not iframe)
    - Optional reload to force server to receive cookie header
    """
    expires = datetime.utcnow() + timedelta(days=days)
    expires_str = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
    safe_value = urllib.parse.quote(value)

    # We set cookie twice:
    # - first without "Secure" (works on localhost http)
    # - then with "Secure" (works on https prod)
    cookie_plain = f"{name}={safe_value}; expires={expires_str}; path=/; SameSite=Lax"
    cookie_secure = f"{name}={safe_value}; expires={expires_str}; path=/; SameSite=Lax; Secure"

    js = f"""
    <script>
      (function() {{
        try {{
          window.top.document.cookie = "{cookie_plain}";
          window.top.document.cookie = "{cookie_secure}";
          console.log("[AUTH] Cookie set (plain+secure):", "{name}");

          {"setTimeout(()=>window.top.location.reload(), 150);" if reload else ""}
        }} catch(e) {{
          console.error("[AUTH] Cookie set failed:", e);
        }}
      }})();
    </script>
    """
    components.html(js, height=0, width=0)


def _set_cookie_and_reload(name: str, value: str, days: int):
    _cookie_js(name, value, days, reload=True)


def _set_cookie_client_side(name: str, value: str, days: int):
    _cookie_js(name, value, days, reload=False)


def _clear_cookie(conf: dict, reason: str | None = None, reload: bool = False):
    _cookie_js(conf["token_name"], "", days=-1, reload=reload)
    if reason:
        st.toast(reason, icon="🔒")


# =========================================================
# G. COOKIE AUTH PIPELINE
# =========================================================
def _auth_from_cookie(conf: dict, cookies: dict) -> tuple[bool, str, str | None, str | None]:
    """
    Returns: ok, reason, user, session_id
    """
    if not conf["key"]:
        return False, "missing_secret_key", None, None

    raw_token = cookies.get(conf["token_name"])
    if not raw_token:
        return False, "no_cookie", None, None

    # URL-decode token (because we encoded it on write)
    token = urllib.parse.unquote(raw_token)

    valid = _validate_token(token, conf["key"])
    if not valid:
        return False, "invalid_token", None, None

    user, sid = valid

    if sid and _is_session_blacklisted(sid):
        return False, "blacklisted", user, sid

    return True, "ok", user, sid


# =========================================================
# H. MAIN GUARD
# =========================================================
def check_login() -> bool:
    """Absolute guard: session cache + idle timeout + cookie auth."""
    if st.session_state.get("_force_logout", False):
        return False

    conf = _get_secrets()

    # 1) Already logged in -> idle timeout check
    if st.session_state.get("logged_in"):
        last_active = st.session_state.get("_last_active_at", 0)
        if last_active > 0:
            elapsed_min = (time.time() - last_active) / 60
            if elapsed_min > conf["idle_timeout_min"]:
                _exec_logout(reason="Session expired due to inactivity. 🕒")
                return False

        st.session_state["_last_active_at"] = time.time()
        return True

    # 2) Read cookies (native Streamlit)
    cookies = st.context.cookies
    # Debug:
    # print(f"[AUTH-CHECK] Cookies: {dict(cookies) if cookies else None}")

    if not cookies:
        return False

    # 3) Validate cookie token
    ok, reason, user, sid = _auth_from_cookie(conf, cookies)
    # print(f"[AUTH-CHECK] Pipeline: ok={ok}, reason={reason}, user={user}")

    if not ok:
        # Clear cookie on invalid token / blacklisted
        if reason in ["invalid_token", "blacklisted"] and cookies.get(conf["token_name"]):
            # ✅ Reload is REQUIRED here because st.context.cookies reads from headers.
            # If we don't reload, the next rerun still sees the old invalid cookie in headers.
            _clear_cookie(conf, reload=True)
        return False

    # 4) Hydrate session state
    st.session_state["logged_in"] = True
    st.session_state["username"] = user
    st.session_state["_last_active_at"] = time.time()

    if conf["superadmin_user"] and user == conf["superadmin_user"]:
        st.session_state["is_superadmin"] = True

    return True


def _exec_logout(reason: str | None = None):
    """Unified logout: blacklist current session_id + clear cookie + cleanup."""
    conf = _get_secrets()

    # blacklist current session_id if valid
    try:
        cookies = st.context.cookies
        raw = cookies.get(conf["token_name"])
        if raw and conf["key"]:
            token = urllib.parse.unquote(raw)
            valid = _validate_token(token, conf["key"])
            if valid:
                _, sid = valid
                if sid:
                    _blacklist_session(sid)
    except Exception:
        pass

    st.session_state["_force_logout"] = True

    # clear cookie hard
    _clear_cookie(conf)

    # clear session
    for k in ["logged_in", "username", "_last_active_at", "is_superadmin"]:
        st.session_state.pop(k, None)

    if reason:
        st.toast(reason, icon="🔒")
        time.sleep(0.5)
    else:
        # Small delay to ensure the JS 'delete cookie' command is received by browser
        # before we rerun and unmount the component
        time.sleep(0.1)

    st.rerun()


# =========================================================
# I. UI COMPONENTS
# =========================================================
def login_page():
    conf = _get_secrets()
    st.session_state["_force_logout"] = False

    st.markdown(
        """
        <style>
            [data-testid="stHeader"], [data-testid="stSidebar"] {visibility: hidden;}
            .block-container {padding-top: 5rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        st.markdown("<div style='text-align:center; font-size:54px;'>🛸</div>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center; margin-bottom:.25rem;'>Admin Portal</h2>", unsafe_allow_html=True)

        with st.container(border=True):
            with st.form("login_form"):
                u = st.text_input("👤 Username", placeholder="e.g. admin")
                p = st.text_input("🔑 Password", type="password", placeholder="••••••••")

                if st.form_submit_button("✨ Sign In", type="primary", use_container_width=True):
                    is_superadmin_login = bool(conf["superadmin_user"] and u == conf["superadmin_user"])

                    if verify_user_password(u, p):
                        if not conf["key"]:
                            st.error("❌ Missing AUTH_COOKIE_SECRET. Cannot create session token.")
                            st.stop()

                        token = _create_token(u, conf["key"], conf["days"])

                        # ✅ Set cookie then reload browser so cookie is included in next request
                        _set_cookie_and_reload(conf["token_name"], token, conf["days"])

                        # Also set session state (nice UX, but cookie is source of truth)
                        st.session_state["logged_in"] = True
                        st.session_state["username"] = u
                        st.session_state["_last_active_at"] = time.time()

                        if is_superadmin_login:
                            st.session_state["is_superadmin"] = True
                            st.success("🔓 Superadmin mode activated!")
                        else:
                            st.success("Authorized! Reloading...")

                        st.stop()
                    else:
                        st.error("❌ Invalid credentials.")



def logout_button():
    """
    Render User Profile Menu (Popover) in Sidebar.
    Contains: Change Password & Logout.
    """
    user = get_current_user()
    if not user: return

    # Modern "Profile" Popover
    with st.sidebar.popover(f"👤 {user}", use_container_width=True):
        st.caption("Account Settings")
        
        if st.button("🔑 Change Password", use_container_width=True):
            show_change_password_dialog()

        st.divider()
        
        # Direct Logout (Fast)
        if st.button("🚪 Sign Out", type="primary", use_container_width=True):
            _exec_logout()



# =========================================================
# J. ROLE HELPERS
# =========================================================
def is_superadmin() -> bool:
    return st.session_state.get("is_superadmin", False)


def get_current_user() -> str:
    return st.session_state.get("username", "")


# =========================================================
# K. ADMIN PASSWORD RESET (SUPERADMIN ONLY)
# =========================================================
@st.dialog("🔐 Reset Admin Password")
def show_reset_password_dialog():
    if not is_superadmin():
        st.error("Access denied. Superadmin only.")
        return

    st.warning("⚠️ This will generate a new password hash for the **admin** account.")
    st.write("Copy the generated hash and update your `AUTH_PASSWORD_HASH` env var.")
    st.write("")

    new_pw = st.text_input("New Password", type="password", placeholder="Enter new admin password")
    confirm_pw = st.text_input("Confirm Password", type="password", placeholder="Confirm password")

    if st.button("Generate Hash", type="primary", use_container_width=True):
        if not new_pw or len(new_pw) < 6:
            st.error("Password must be at least 6 characters.")
        elif new_pw != confirm_pw:
            st.error("Passwords do not match.")
        else:
            new_hash = generate_password_hash(new_pw)
            st.success("✅ Hash generated! Copy below:")
            st.code(new_hash, language="text")
            st.info("Update `AUTH_PASSWORD_HASH` then restart app.")


# =========================================================
# L. SELF-SERVICE PASSWORD CHANGE (ALL USERS)
# =========================================================
@st.dialog("🔑 Change Password")
def show_change_password_dialog():
    current_user = get_current_user()
    if not current_user:
        st.error("Not logged in.")
        return

    st.write(f"Changing password for: **{current_user}**")
    st.write("")

    current_pw = st.text_input("Current Password", type="password", placeholder="Enter current password")
    new_pw = st.text_input("New Password", type="password", placeholder="Enter new password (min 6 chars)")
    confirm_pw = st.text_input("Confirm New Password", type="password", placeholder="Confirm new password")

    if st.button("💾 Update Password", type="primary", use_container_width=True):
        if not verify_user_password(current_user, current_pw):
            st.error("❌ Current password is incorrect.")
            return

        if not new_pw or len(new_pw) < 6:
            st.error("New password must be at least 6 characters.")
            return

        if new_pw != confirm_pw:
            st.error("New passwords do not match.")
            return

        new_hash = generate_password_hash(new_pw)
        if _set_db_password_hash(current_user, new_hash):
            st.success("✅ Password changed successfully!")
            st.info("Your new password is now active.")
            time.sleep(0.8)
            st.rerun()
        else:
            st.error("Failed to save new password. Please try again.")
