"""
Analytics UI Components — Rendering functions for dashboard widgets.
Each function renders one visual section of the dashboard.
"""
import streamlit as st
import json
import altair as alt
from datetime import datetime, date
from typing import List, Dict, Optional, Any

from modules import db, pdf_report
from ui.formatters import rupiah
from services.analytics_service import get_cell_color, parse_date_safe
from services.analytics_agg import (
    aggregate_monthly_data,
    aggregate_daily_data,
    aggregate_daily_details,
    find_top_item,
)

SECTION_GAP = "20px"
CARD_PADDING = "10px"


# =============================================================================
# PDF HELPERS — Cached
# =============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def _get_yearly_report_pdf(year: int) -> Optional[bytes]:
    try:
        data = db.get_yearly_report_data(year)
        if not data:
            return None
        chart_data = db.get_analytics_revenue_trend(year)
        return pdf_report.generate_yearly_report(data, year, chart_data=chart_data).getvalue()
    except Exception as e:
        print(f"[Analytics] Yearly report error: {e}")
        return None


@st.cache_data(ttl=300, show_spinner=False)
def _get_monthly_report_pdf(year: int, month: int) -> Optional[bytes]:
    try:
        data = db.get_monthly_report_data(year, month)
        if not data:
            return None
        return pdf_report.generate_monthly_report(data, year, month).getvalue()
    except Exception as e:
        print(f"[Analytics] Monthly report error: {e}")
        return None


# =============================================================================
# DATA HEALTH PANEL
# =============================================================================

def render_data_health_panel(meta: Dict[str, Any]) -> None:
    """Debug panel showing data quality metrics."""
    with st.expander("🛡 Data Health & Quality (Debug)", expanded=False):
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Total Loaded", meta.get("total_loaded", 0))
        d2.metric("Skipped Rows", meta.get("skipped_rows", 0), help="Invalid dates or corrupted rows")
        d3.metric("Negative Values Fix", meta.get("negative_sanitized", 0), help="Sanitized negative amounts")
        d4.metric("Items Skipped", meta.get("items_skipped", 0))
        st.caption(f"Unique Clients: {len(meta.get('unique_clients', []))} | Unique Venues: {len(meta.get('unique_venues', []))}")


# =============================================================================
# KPI CARDS
# =============================================================================

def render_kpi_cards(
    bookings: List[Dict],
    kpi: Dict[str, Any],
    selected_year: int,
    available_years: List[int],
    current_target: float,
) -> tuple:
    """
    Render the KPI card rows. Returns (selected_year, selected_month) from user inputs.
    """
    current_month = datetime.now().month

    # ===== ROW 1: Yearly + Monthly (2 columns) =====
    k1, k2 = st.columns(2)

    with k1:
        with st.container(border=True):
            st.write("📅 **Yearly Overview**")
            selected_year = st.selectbox(
                "Select Year", options=available_years, index=0,
                label_visibility="collapsed", key="year_selector"
            )

            total_rev = kpi["total_rev"]
            prev_rev = kpi["prev_rev"]
            growth = kpi["growth"]

            growth_html = ""
            if growth is not None:
                color = "#166534" if growth >= 0 else "#dc2626"
                icon = "⬆" if growth >= 0 else "⬇"
                growth_html = f"<div style='color:{color}; font-size:0.8rem; margin-top:4px;'>{icon} {growth:.1f}% vs Last Year</div>"
            else:
                growth_html = "<div style='color:#6b7280; font-size:0.8rem; margin-top:4px;'>No Data Last Year</div>"

            st.markdown(f"""
                <div style="margin-top: {CARD_PADDING};">
                    <div style="font-size: 0.85rem; color: #166534; font-weight: 600;">Total Revenue</div>
                    <div style="font-size: 1.6rem; font-weight: 700; color: #15803d;">{rupiah(total_rev)}</div>
                    {growth_html}
                </div>
            """, unsafe_allow_html=True)

            st.markdown(f"<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)

            try:
                pdf_bytes = _get_yearly_report_pdf(selected_year)
                if pdf_bytes:
                    st.download_button("📥 Download Report", data=pdf_bytes,
                        file_name=f"Report_{selected_year}.pdf", mime="application/pdf",
                        key=f"yr_{selected_year}", use_container_width=True)
                else:
                    st.button("📥 No Data", disabled=True, use_container_width=True, key=f"no_yr_{selected_year}")
            except Exception as e:
                st.error(f"Generate Failed: {e}")

            st.markdown("<div style='height:4px; width:100%; background:#bbf7d0; margin-top:10px; border-radius:2px;'></div>", unsafe_allow_html=True)

    with k2:
        with st.container(border=True):
            st.write("🗓️ **Monthly Detail**")
            current_month_idx = max(0, min(11, current_month - 1))
            selected_month = st.selectbox(
                "Select Month", options=range(1, 13), index=current_month_idx,
                format_func=lambda x: datetime(2000, x, 1).strftime("%B"),
                label_visibility="collapsed", key="month_selector"
            )

            month_name = datetime(2000, selected_month, 1).strftime("%B")
            mo_rev = kpi["mo_rev"]
            mo_count = kpi["mo_count"]

            st.markdown(f"""
                <div style="margin-top: {CARD_PADDING};">
                    <div style="font-size: 0.85rem; color: #6b21a8; font-weight: 600;">Revenue ({month_name})</div>
                    <div style="font-size: 1.6rem; font-weight: 700; color: #7e22ce;">{rupiah(mo_rev)}</div>
                    <div style="font-size: 0.85rem; color: #a855f7; margin-top:4px;">{mo_count} Invoice{"" if mo_count == 1 else "s"}</div>
                </div>
            """, unsafe_allow_html=True)

            st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)

            try:
                pdf_bytes_mo = _get_monthly_report_pdf(selected_year, selected_month)
                if pdf_bytes_mo:
                    st.download_button("📥 Download Report", data=pdf_bytes_mo,
                        file_name=f"Report_{selected_year}_{selected_month:02d}.pdf", mime="application/pdf",
                        key=f"mo_{selected_year}_{selected_month}", use_container_width=True)
                else:
                    st.button("📥 No Data", disabled=True, use_container_width=True, key=f"no_mo_{selected_year}_{selected_month}")
            except Exception as e:
                st.error(f"Generate Failed: {e}")

            st.markdown("<div style='height:4px; width:100%; background:#e9d5ff; margin-top:10px; border-radius:2px;'></div>", unsafe_allow_html=True)

    return selected_year, selected_month


def render_top_insights(kpi: Dict[str, Any], month_name: str, current_target: float) -> None:
    """Render the top insights horizontal card row."""
    pct = kpi["pct"]
    grow_col = "#16a34a" if pct >= 100 else "#dc2626"
    mo_rev = kpi["mo_rev"]

    with st.container(border=True):
        st.write("🏆 **Top Insights**")
        c1, c2, c3, c4, c5, c6 = st.columns(6)

        _cards = [
            (c1, f"Target ({month_name})", rupiah(mo_rev), f"of {rupiah(current_target)}", "#1d4ed8"),
            (c2, f"Status ({month_name})", f"{pct:.1f}%", "Achieved", grow_col),
            (c3, "Top Month", kpi["top_month"], rupiah(kpi["top_month_rev"]), "#1d4ed8"),
            (c4, "Total Invoices", str(kpi["total_invoices"]), "this year", "#1d4ed8"),
            (c5, "Top Venue", kpi["top_venue"], f"{kpi['top_venue_cnt']} Event{'s' if kpi['top_venue_cnt'] != 1 else ''}", "#1d4ed8"),
            (c6, "Top Package", kpi["top_pkg"], f"{kpi['top_pkg_cnt']} Sold", "#1d4ed8"),
        ]

        for col, label, value, sub, color in _cards:
            with col:
                overflow = "white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" if label in ("Top Venue", "Top Package") else ""
                st.markdown(f"""<div style="padding:8px; background:#eff6ff; border-radius:6px; text-align:center;">
<div style="font-size:0.65rem; color:#1e40af; font-weight:600; text-transform:uppercase;">{label}</div>
<div style="font-size:{'0.85rem' if overflow else '1rem'}; font-weight:700; color:{color}; margin-top:4px; {overflow}">{value}</div>
<div style="font-size:0.65rem; color:#60a5fa;">{sub}</div>
</div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:4px; width:100%; background:#bfdbfe; margin-top:10px; border-radius:2px;'></div>", unsafe_allow_html=True)


# =============================================================================
# REVENUE CHART
# =============================================================================

def render_revenue_chart(bookings: List[Dict], selected_year: int, current_target: float, mo_rev: float) -> None:
    """Render the Altair revenue bar chart with target line."""
    st.markdown(f"<div style='margin-top: {SECTION_GAP};'></div>", unsafe_allow_html=True)
    st.subheader(f"📈 Revenue Trends ({selected_year})")

    # Target Settings
    with st.expander("🎯 Target Settings", expanded=False):
        col_t1, col_t2 = st.columns([1, 2])
        with col_t1:
            try:
                new_target = st.number_input("Monthly Revenue Target (Rp)",
                    min_value=0.0, value=current_target, step=1000000.0, key="target_input")
                if new_target != current_target:
                    db.set_config("monthly_target", str(new_target))
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
        with col_t2:
            pct = (mo_rev / current_target * 100) if current_target > 0 else 0
            emoji = "✅" if pct >= 100 else "📊"
            st.caption(f"**Current Progress:** {rupiah(mo_rev)} / {rupiah(current_target)} ({pct:.1f}%) {emoji}")

    monthly_dict = aggregate_monthly_data(bookings, selected_year)
    chart_data = [{"month": m, "amount": a} for m, a in monthly_dict.items()]

    try:
        bars = alt.Chart(alt.Data(values=chart_data)).mark_bar(
            cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#10b981"
        ).encode(
            x=alt.X("month:N", sort=None, axis=alt.Axis(labelAngle=0, title=None, grid=False)),
            y=alt.Y("amount:Q", axis=alt.Axis(format=",.0f", title=None, grid=True, tickCount=5)),
            tooltip=[
                alt.Tooltip("month:N", title="Bulan"),
                alt.Tooltip("amount:Q", format=",.0f", title="Pendapatan"),
            ],
        )

        if current_target > 0:
            target_line = alt.Chart(alt.Data(values=[{"target": current_target}])).mark_rule(
                color="#ef4444", strokeDash=[8, 4], strokeWidth=2
            ).encode(y="target:Q", tooltip=[alt.Tooltip("target:Q", format=",.0f", title="🎯 Target")])
            chart = (bars + target_line).properties(height=300)
        else:
            chart = bars.properties(height=300)

        st.altair_chart(chart, use_container_width=True)
    except Exception as e:
        st.error(f"Error rendering chart: {e}")


# =============================================================================
# EVENT CALENDAR
# =============================================================================

def render_event_calendar(bookings_curr: List[Dict], selected_year: int) -> None:
    """Render the monthly calendar grid inside an isolated iframe to reduce main DOM nodes."""
    import streamlit.components.v1 as components

    st.markdown(f"<div style='margin-top: {SECTION_GAP};'></div>", unsafe_allow_html=True)

    cc1, cc2 = st.columns([2, 1])
    with cc1:
        st.subheader(f"📅 Event Calendar ({selected_year})")
    with cc2:
        show_full_year = st.toggle("Show Full Year", value=False, help="Toggle to show all 12 months or just active months")

    daily_counts = aggregate_daily_data(bookings_curr)
    daily_details = aggregate_daily_details(bookings_curr)

    if not daily_counts:
        st.info("📭 No events scheduled for this year yet.")
        return

    try:
        import calendar as cal

        max_count = max(daily_counts.values()) if daily_counts.values() else 1

        # Determine months
        if show_full_year:
            months_to_render = list(range(1, 13))
        else:
            months_with_data = set(b.get("month") for b in bookings_curr if b.get("month"))
            now = datetime.now()
            if selected_year == now.year:
                months_with_data.add(now.month)
                if now.month < 12:
                    months_with_data.add(now.month + 1)
            months_to_render = sorted(months_with_data) if months_with_data else [1]

        # Build ONE self-contained HTML with all months + CSS
        month_htmls = []
        for month_num in months_to_render:
            m_name = date(selected_year, month_num, 1).strftime("%B")
            month_cal = cal.monthcalendar(selected_year, month_num)

            mh = f'<div class="month-card"><div class="month-title">{m_name}</div>'
            mh += '<div class="day-headers">'
            for dn in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]:
                mh += f'<div class="day-hdr">{dn}</div>'
            mh += '</div><div class="day-grid">'

            for week in month_cal:
                for day in week:
                    if day == 0:
                        mh += '<div class="day-empty"></div>'
                    else:
                        day_date = date(selected_year, month_num, day)
                        count = daily_counts.get(day_date, 0)
                        details = daily_details.get(day_date, [])
                        bg = get_cell_color(count, max(1, max_count))
                        tc = "#fff" if count > 0 else "#94a3b8"

                        if count == 0:
                            tt = f"📅 {day_date.strftime('%b %d')}<br>No events"
                        else:
                            tt = f"📅 <b>{day_date.strftime('%b %d')}</b><br>{count} event(s)<br>"
                            for evt in details[:3]:
                                tt += f"• {evt['client']} @ {evt['venue']}<br>"
                            if len(details) > 3:
                                tt += f"<i>+{len(details)-3} more...</i>"

                        mh += f'<div class="cal-day" style="background:{bg};color:{tc};">'
                        mh += f'<div class="tooltip">{tt}</div>{day}</div>'

            mh += '</div></div>'
            month_htmls.append(mh)

        # Compute grid columns
        n_cols = min(4, len(months_to_render))

        full_html = f"""<!DOCTYPE html>
<html><head><style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:transparent;padding:8px 0;}}
.cal-grid{{display:grid;grid-template-columns:repeat({n_cols},1fr);gap:12px;}}
.month-card{{border:1px solid #e5e7eb;border-radius:8px;padding:12px;background:#fff;}}
.month-title{{font-weight:600;color:#166534;margin-bottom:8px;font-size:0.85rem;text-align:center;}}
.day-headers{{display:grid;grid-template-columns:repeat(7,1fr);gap:2px;margin-bottom:6px;}}
.day-hdr{{text-align:center;font-size:0.6rem;color:#9ca3af;font-weight:600;}}
.day-grid{{display:grid;grid-template-columns:repeat(7,1fr);gap:3px;}}
.day-empty{{aspect-ratio:1;}}
.cal-day{{aspect-ratio:1;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:0.65rem;font-weight:600;cursor:pointer;position:relative;transition:transform 0.15s ease;}}
.cal-day:hover{{transform:scale(1.2);z-index:100;}}
.tooltip{{visibility:hidden;opacity:0;position:absolute;bottom:130%;left:50%;transform:translateX(-50%);background:#1f2937;color:#fff;padding:8px 12px;border-radius:6px;font-size:11px;white-space:pre-line;min-width:140px;max-width:200px;box-shadow:0 4px 12px rgba(0,0,0,0.2);z-index:1000;transition:opacity 0.2s;pointer-events:none;}}
.tooltip::after{{content:'';position:absolute;top:100%;left:50%;transform:translateX(-50%);border:6px solid transparent;border-top-color:#1f2937;}}
.cal-day:hover .tooltip{{visibility:visible;opacity:1;}}
.legend{{display:flex;align-items:center;gap:10px;margin-top:12px;font-size:0.75rem;color:#6b7280;justify-content:center;}}
.legend-box{{width:18px;height:18px;border-radius:4px;}}
</style></head><body>
<div class="cal-grid">{"".join(month_htmls)}</div>
<div class="legend">
<span>Less</span>
<div class="legend-box" style="background:#f3f4f6;border:1px solid #e5e7eb;"></div>
<div class="legend-box" style="background:#d1fae5;"></div>
<div class="legend-box" style="background:#6ee7b7;"></div>
<div class="legend-box" style="background:#34d399;"></div>
<div class="legend-box" style="background:#10b981;"></div>
<span>More</span>
</div>
</body></html>"""

        # Calculate height: ~220px per row of months + 40px legend
        n_rows = (len(months_to_render) + n_cols - 1) // n_cols
        iframe_height = n_rows * 230 + 50

        components.html(full_html, height=iframe_height, scrolling=False)

    except Exception as e:
        st.error(f"Error rendering calendar: {e}")


# =============================================================================
# QUICK JUMP NAVIGATOR
# =============================================================================

def render_quick_jump(bookings_curr: List[Dict]) -> None:
    """Render the quick event navigator with edit functionality."""
    if not bookings_curr:
        return

    st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.caption("🚀 **Quick Jump to Event**")

        c_month, c_evt, c_btn = st.columns([1, 2.5, 1], vertical_alignment="bottom")

        with c_month:
            months_in_data = sorted({b.get("month") for b in bookings_curr if b.get("month")})
            if not months_in_data:
                st.info("No month data available.")
                return

            month_options = [date(2000, m, 1).strftime("%B") for m in months_in_data]
            selected_month_name = st.selectbox("Filter Month", options=month_options,
                index=0, key="qj_month_filter", label_visibility="collapsed")

        with c_evt:
            month_num = datetime.strptime(selected_month_name, "%B").month
            filtered = [b for b in bookings_curr if b["month"] == month_num]
            sorted_evts = sorted(filtered, key=lambda x: x["date_str"])

            if not sorted_evts:
                st.info("No events in this month.")
                selected_evt_id = None
            else:
                selected_evt_id = st.selectbox("Select Event",
                    options=[b["id"] for b in sorted_evts],
                    format_func=lambda x: next(
                        (f"📅 {b['date_str']} | {b['client_name']} @ {b['venue']}" for b in sorted_evts if b["id"] == x),
                        "Unknown"
                    ),
                    key="quick_nav_evt", label_visibility="collapsed")

        with c_btn:
            if st.button("✏️ Edit Invoice", use_container_width=True, type="primary"):
                if selected_evt_id:
                    _handle_quick_edit(selected_evt_id)


def _handle_quick_edit(invoice_id: int) -> None:
    """Load invoice into session state for editing. No locale dependency."""
    try:
        detail = db.get_invoice_details(invoice_id)
        if not detail:
            st.error("Invoice data not found.")
            return

        payload = json.loads(detail["invoice_data"])
        meta = payload.get("meta", {})

        # Restore basic fields
        st.session_state["inv_items"] = payload.get("items", [])
        st.session_state["inv_no"] = meta.get("inv_no", "")
        st.session_state["inv_title"] = meta.get("title", "")
        st.session_state["inv_client_name"] = meta.get("client_name", "")
        st.session_state["inv_client_phone"] = meta.get("client_phone", "")
        st.session_state["inv_client_email"] = meta.get("client_email", "")
        st.session_state["inv_venue"] = meta.get("venue", "")

        # Date: pure strptime, NO locale hack
        w_date_str = meta.get("wedding_date", "")
        if w_date_str:
            parsed = parse_date_safe(w_date_str)
            if parsed:
                st.session_state["inv_wedding_date"] = w_date_str  # Keep as string for the UI picker

        st.session_state["inv_hours"] = meta.get("hours", "")
        st.session_state["inv_cashback"] = float(meta.get("cashback", 0))

        # Payment terms
        pt = meta.get("payment_terms")
        st.session_state["payment_terms"] = pt if pt else []

        # Defaults fallback for legacy invoices
        from modules.invoice_state import load_db_settings
        defaults = load_db_settings()

        st.session_state["inv_terms"] = meta.get("terms") or defaults["terms"]
        st.session_state["bank_nm"] = meta.get("bank_name") or defaults["bank_nm"]
        st.session_state["bank_ac"] = meta.get("bank_acc") or defaults["bank_ac"]
        st.session_state["bank_an"] = meta.get("bank_holder") or defaults["bank_an"]
        st.session_state["inv_footer"] = meta.get("footer") or defaults["inv_footer"]
        st.session_state["wa_template"] = meta.get("wa_template") or db.get_config("wa_template_default") or ""

        pp = meta.get("payment_proof")
        st.session_state["pp_cached"] = [pp] if pp and not isinstance(pp, list) else (pp or [])

        # Navigate to edit mode
        st.session_state["editing_invoice_id"] = invoice_id
        st.session_state["menu_selection"] = "🧾 Create Invoice"
        st.session_state["nav_key"] = st.session_state.get("nav_key", 0) + 1
        st.rerun()

    except Exception as e:
        st.error(f"Failed to load invoice: {e}")
