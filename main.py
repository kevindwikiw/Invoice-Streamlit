# main.py
import time
import streamlit as st
from config import settings, theme

# =========================================================
# 1. PAGE CONFIG (Global Scope - First Command)
# =========================================================
st.set_page_config(
    page_title=settings.PAGE_TITLE, 
    layout=settings.PAGE_LAYOUT,
    initial_sidebar_state="expanded"
)

# Imports after page_config
from modules import auth, db
from views import packages_view, invoice_view, history_view

# =========================================================
# 2. INITIALIZATION ROUTINES
# =========================================================
def init_application():
    """Initializes Theme and Database connection."""
    st.markdown(theme.CSS, unsafe_allow_html=True)
    
    # Initialize DB (Singleton pattern)
    if not st.session_state.get("_db_initialized", False):
        db.init_db()
        st.session_state["_db_initialized"] = True
    
    # Init dynamic nav key
    if "nav_key" not in st.session_state:
        st.session_state["nav_key"] = 0

# =========================================================
# 3. UI COMPONENTS
# =========================================================
@st.dialog("🚨 Factory Reset")
def show_factory_reset_dialog():
    st.error("WARNING: Irreversible Action")
    st.caption("This will delete **ALL** packages.")
    
    confirm = st.text_input("Type **CONFIRM** to proceed:")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancel", use_container_width=True):
            st.rerun()
    with c2:
        if st.button("💣 Delete All", type="primary", disabled=(confirm != "CONFIRM"), use_container_width=True):
            db.delete_all_packages()
            st.success("System reset successful.")
            time.sleep(1.0)
            st.rerun()

def render_sidebar() -> str:
    with st.sidebar:
        st.markdown("## 🧭 Admin Panel")

        # User Card
        username = st.session_state.get("username", "Admin")
        st.markdown(
            f"""
            <div style="
              display:flex; justify-content:space-between; align-items:center;
              padding:12px 14px; border:1px solid var(--border); border-radius:12px;
              background:#fff; margin-top:8px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
              <div style="display:flex; align-items:center; gap: 10px;">
                <div style="font-size: 20px;">👤</div>
                <div>
                    <div style="font-weight:700; color:#333; line-height:1.2;">{username}</div>
                    <div style="color:#2ecc71; font-size:11px; font-weight:600;">● Online</div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write("")

        # Stats
        try:
            packages = db.load_packages()
            pkg_count = len(packages)
            db_empty = (pkg_count == 0)
            
            # Fetch Dashboard Stats
            stats = db.get_dashboard_stats()
            total_rev = stats.get("revenue", 0)
            inv_count = stats.get("count", 0)
            
        except Exception:
            pkg_count = 0
            db_empty = True
            total_rev = 0
            inv_count = 0

        # Mini Dashboard
        m1, m2 = st.columns(2)
        m1.metric("Packages", str(pkg_count))
        m2.metric("Invoices", str(inv_count))
        
        # Helper for format
        def _fmt_rev(val):
            if val >= 1_000_000_000:
                return f"Rp{val/1_000_000_000:.1f}M"
            elif val >= 1_000_000:
                return f"Rp{val/1_000_000:.1f}Jt"
            return f"Rp{val:,.0f}"
            
        st.metric("Total Revenue", _fmt_rev(total_rev), help="Total from all saved invoices")
        st.divider()

        # Navigation
        nav_options = ["📦 Package Database"]
        if not db_empty:
             nav_options.append("🧾 Create Invoice")
             nav_options.append("📜 Invoice History")
        
        # State Persistence
        current_selection = st.session_state.get("menu_selection", nav_options[0])
        if current_selection not in nav_options: 
            current_selection = nav_options[0]
        
        selected = st.radio(
            "Main Menu", 
            options=nav_options, 
            index=nav_options.index(current_selection),
            key=f"nav_radio_{st.session_state['nav_key']}",
            label_visibility="collapsed"
        )
        st.session_state["menu_selection"] = selected

        if db_empty:
             st.info("💡 Add a package to unlock Invoicing.")

        st.divider()

        # Auth & Tools
        auth.logout_button()
        
        with st.expander("🛠️ System Tools"):
            if st.button("🔴 Factory Reset", use_container_width=True):
                show_factory_reset_dialog()

        return selected

# =========================================================
# 4. MAIN EXECUTION
# =========================================================
def main():
    
    # 1. Setup
    init_application()

    # 2. AUTH GUARD (Stops execution if not logged in)
    if not auth.check_login():
        auth.login_page()
        st.stop() 

    # 3. AUTHORIZED ZONE
    selected_menu = render_sidebar()

    if selected_menu == "📦 Package Database":
        packages_view.render_page()
        
    elif selected_menu == "🧾 Create Invoice":
        if db.is_db_empty():
            st.error("Database is empty. Please add packages first.")
            if st.button("Back to Database"):
                 st.session_state["menu_selection"] = "📦 Package Database"
                 st.rerun()
        else:
            invoice_view.render_page()

    elif selected_menu == "📜 Invoice History":
        history_view.render_page()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error("An unexpected system error occurred.")
        with st.expander("Admin Details"):
            st.code(str(e))
