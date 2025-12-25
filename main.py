# main.py
import time
import streamlit as st
from config import settings, theme
from modules import auth, db
from views import packages_view, invoice_view

# =========================
# 0) GLOBAL DIALOGS
# =========================
@st.dialog("🚨 Factory Reset")
def show_factory_reset_dialog():
    st.error("PERINGATAN: Ini akan menghapus **SELURUH** data paket.")
    st.caption("Gunakan hanya untuk dev/testing.")
    confirm = st.text_input("Ketik **CONFIRM** untuk melanjutkan:")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancel", use_container_width=True):
            st.rerun()
    with c2:
        if st.button(
            "💣 Hapus Semuanya",
            type="primary",
            disabled=(confirm != "CONFIRM"),
            use_container_width=True,
        ):
            try:
                db.delete_all_packages()
                st.success("Sistem berhasil di-reset.")
                time.sleep(0.5) # Beri waktu user membaca success message
                st.rerun()
            except Exception as e:
                st.error("Gagal reset database.")
                st.caption(f"Debug: {e}")

# =========================
# 1) APP INIT
# =========================
def init_app():
    st.set_page_config(page_title=settings.PAGE_TITLE, layout=settings.PAGE_LAYOUT)
    
    # Theme single source
    st.markdown(theme.CSS, unsafe_allow_html=True)

    # Init DB once per session
    if not st.session_state.get("_db_inited", False):
        db.init_db()
        st.session_state["_db_inited"] = True

# =========================
# 2) SIDEBAR UI
# =========================
def _sidebar() -> str:
    with st.sidebar:
        st.markdown("## 🧭 Admin Panel")

        username = st.session_state.get("username", "Admin")

        # Status chip (Visual User Card)
        st.markdown(
            f"""
            <div style="
              display:flex; justify-content:space-between; align-items:center;
              padding:10px 12px; border:1px solid var(--border); border-radius:12px;
              background:#fff; margin-top:8px;">
              <div>
                <div style="font-weight:900; color:var(--text); line-height:1.1;">{username}</div>
                <div style="color:var(--muted); font-size:.85rem; margin-top:3px;">Signed in</div>
              </div>
              <div style="
                width:10px; height:10px; border-radius:999px; background:#2ecc71;
                box-shadow:0 0 0 4px rgba(46,204,113,.14);"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.write("")

        # Quick stats & DB Check
        try:
            packages = db.load_packages()
            pkg_count = len(packages)
            db_empty = pkg_count == 0
        except Exception:
            pkg_count = 0
            db_empty = True

        st.markdown(
            f"""
            <div style="
              padding:12px; border:1px solid var(--border); border-radius:12px;
              background: var(--soft);">
              <div style="color:var(--muted); font-size:.78rem; letter-spacing:.06em; font-weight:900; text-transform:uppercase;">
                Summary
              </div>
              <div style="display:flex; justify-content:space-between; margin-top:10px;">
                <div style="color:var(--muted);">Packages</div>
                <div style="font-weight:900; color:var(--text);">{pkg_count}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()

        # --- NAVIGATION LOGIC IMPROVED ---
        
        # 1. Tentukan opsi yang tersedia berdasarkan kondisi DB
        nav_options = ["📦 Package Database"]
        if not db_empty:
            nav_options.append("🧾 Create Invoice")
        
        # 2. Handle state jika user sebelumnya di halaman invoice lalu DB dihapus
        current_menu = st.session_state.get("menu", nav_options[0])
        if current_menu not in nav_options:
            current_menu = nav_options[0]

        # 3. Render Radio Button
        # Kita gunakan index berdasarkan current_menu yang valid
        try:
            idx = nav_options.index(current_menu)
        except ValueError:
            idx = 0

        selected = st.radio(
            "Navigation", 
            options=nav_options, 
            index=idx, 
            key="menu_radio"
        )

        # Update session state
        st.session_state["menu"] = selected

        # Show warning if needed (hanya visual, karena opsi invoice sudah hilang)
        if db_empty:
             st.caption("⚠️ *Menu Invoice terkunci karena database kosong.*")

        st.divider()

        # Logout
        auth.logout_button()

        # Dev tools
        with st.expander("⚙️ Dev Tools"):
            if st.button("🔴 Factory Reset", use_container_width=True):
                show_factory_reset_dialog()

        return selected

# =========================
# 3) ROUTING
# =========================
def main():
    init_app()

    # Smooth cookie readiness
    auth.boot_gate()

    # Auth guard
    if not auth.check_login():
        auth.login_page()
        st.stop()

    # Render Sidebar & Get Selection
    menu = _sidebar()

    # Router
    if menu == "📦 Package Database":
        packages_view.render_page()
    elif menu == "🧾 Create Invoice":
        # Double check safety (meskipun sidebar sudah handle)
        if db.is_db_empty():
            st.error("Database kosong. Mohon input paket terlebih dahulu.")
            if st.button("Kembali ke Database"):
                 st.session_state["menu"] = "📦 Package Database"
                 st.rerun()
        else:
            invoice_view.render_page()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Global Error Boundary agar app tidak crash total layar putih
        st.error("Terjadi kesalahan sistem.")
        st.expander("Detail Error").code(str(e))