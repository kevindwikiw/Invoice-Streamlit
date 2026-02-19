"""
Analytics Dashboard — Orchestrator.
Thin layer that wires data loading, aggregation, and UI components together.
"""
import streamlit as st
from datetime import datetime
from typing import Any

from modules import db
from views.styles import page_header, inject_styles
from services.analytics_service import load_analytics_data
from services.analytics_agg import compute_kpi_data
from views.analytics_components import (
    render_data_health_panel,
    render_kpi_cards,
    render_top_insights,
    render_revenue_chart,
    render_event_calendar,
    render_quick_jump,
)


def render_page() -> None:
    """Render the analytics dashboard."""
    inject_styles()
    page_header("📊 Analytics Dashboard", "Business insights and performance metrics.")

    # 1. Load data (cached, cloud-safe)
    try:
        version_key = db.get_analytics_version()
    except Exception:
        version_key = None

    data_pkg = load_analytics_data(_version_key=version_key)
    bookings = data_pkg.get("bookings", [])
    items = data_pkg.get("items", [])
    meta = data_pkg.get("meta", {})

    if not bookings:
        st.info("📭 No analytics data available yet. Create your first invoice to see insights!")
        return

    # 2. Debug panel
    render_data_health_panel(meta)

    # 3. Config
    current_year = datetime.now().year
    current_month = datetime.now().month

    try:
        current_target = float(db.get_config("monthly_target", "50000000"))
    except (ValueError, TypeError):
        current_target = 50000000.0

    available_years = sorted(
        {b.get("year") for b in bookings if isinstance(b.get("year"), int)},
        reverse=True,
    )
    if not available_years:
        available_years = [current_year]

    # 4. Compute KPIs (first pass with defaults, re-compute after user selects year/month)
    kpi = compute_kpi_data(bookings, items, available_years[0], current_month, current_target)

    # 5. KPI Cards (returns user-selected year/month)
    selected_year, selected_month = render_kpi_cards(
        bookings, kpi, available_years[0], available_years, current_target
    )

    # 6. Re-compute KPIs with actual user selection
    kpi = compute_kpi_data(bookings, items, selected_year, selected_month, current_target)

    # 7. Top Insights
    month_name = datetime(2000, selected_month, 1).strftime("%B")
    render_top_insights(kpi, month_name, current_target)

    # 8. Revenue Chart
    render_revenue_chart(bookings, selected_year, current_target, kpi["mo_rev"])

    # 9. Event Calendar
    render_event_calendar(kpi["bookings_curr"], selected_year)

    # 10. Quick Jump Navigator
    render_quick_jump(kpi["bookings_curr"])
