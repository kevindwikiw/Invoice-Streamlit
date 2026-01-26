
import streamlit as st
from modules import db

def render_db_status() -> None:
    """Renders the database connection status (Postgres vs SQLite) at the bottom of sidebar."""
    db_type = db.get_adapter_type()
    
    # Styling based on type
    if db_type == "Postgres":
        color = "#10b981" # Green
        icon = "🟢"
        label = "Cloud (Supabase)"
    else:
        color = "#f59e0b" # Amber
        icon = "🟠"
        label = "Local (SQLite)"

    # Use a small container at the bottom
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"""
        <div style="display:flex; align-items:center; justify-content:space-between; font-size:0.75rem; color:#6b7280;">
            <span>System Status</span>
            <span style="color:{color}; font-weight:600;">{icon} {label}</span>
        </div>
        """, 
        unsafe_allow_html=True
    )
