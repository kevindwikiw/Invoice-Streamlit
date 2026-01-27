import streamlit as st
import json
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict
import altair as alt
from modules import db, pdf_report
from views.styles import page_header, inject_styles
from ui.formatters import rupiah

# =============================================================================
# CONSTANTS
# =============================================================================

SECTION_GAP = "20px"
CARD_PADDING = "10px"
DEFAULT_VENUE = "Unknown"
DEFAULT_PACKAGE = "Unknown"
HEATMAP_COLORS = ["#f3f4f6", "#d1fae5", "#a7f3d0", "#6ee7b7", "#34d399", "#10b981"]


# =============================================================================
# HELPER FUNCTIONS - Date Parsing
# =============================================================================

def _parse_date_safe(date_str: Optional[str]) -> Optional[datetime]:
    """
    Safely parse a date string with multiple format fallbacks.
    
    Args:
        date_str: Date string to parse (can be None or empty)
        
    Returns:
        Parsed datetime object or None if parsing fails
        
    Examples:
        >>> _parse_date_safe("Sunday, 12 January 2025")
        datetime(2025, 1, 12, 0, 0)
        >>> _parse_date_safe("2025-01-12")
        datetime(2025, 1, 12, 0, 0)
        >>> _parse_date_safe(None)
        None
    """
    if not date_str or not isinstance(date_str, str):
        return None
    
    # Format 1: "Sunday, 12 January 2025"
    try:
        return datetime.strptime(date_str, "%A, %d %B %Y")
    except (ValueError, TypeError):
        pass
    
    # Format 2: "YYYY-MM-DD"
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        pass
    
    # Format 3: ISO format fallback
    try:
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        pass
        
    return None


# =============================================================================
# HELPER FUNCTIONS - Data Aggregation
# =============================================================================

def _aggregate_monthly_data(bookings: List[Dict], year: int) -> Dict[str, float]:
    """
    Aggregate booking amounts by month for a specific year.
    
    Args:
        bookings: List of booking dictionaries
        year: Target year for aggregation
        
    Returns:
        Dictionary mapping month abbreviations to total amounts (non-negative)
    """
    monthly_data = {datetime(2000, m, 1).strftime('%b'): 0.0 for m in range(1, 13)}
    
    for booking in bookings:
        if booking.get('year') == year:
            month_name = booking.get('month_name', '')[:3]
            if month_name in monthly_data:
                amount = booking.get('amount', 0)
                # Safe amount addition - ensure non-negative
                try:
                    monthly_data[month_name] += max(0.0, float(amount))
                except (ValueError, TypeError):
                    pass  # Skip invalid amounts
    
    # Final sanitization: ensure all values are non-negative
    for month in monthly_data:
        monthly_data[month] = max(0.0, monthly_data[month])
                    
    return monthly_data


def _aggregate_daily_data(bookings: List[Dict]) -> Dict[date, int]:
    """
    Count bookings per day.
    
    Args:
        bookings: List of booking dictionaries
        
    Returns:
        Dictionary mapping dates to event counts
    """
    daily_counts = defaultdict(int)
    
    for booking in bookings:
        date_obj = booking.get('date_obj')
        if isinstance(date_obj, datetime):
            daily_counts[date_obj.date()] += 1
            
    return dict(daily_counts)


def _aggregate_daily_details(bookings: List[Dict]) -> Dict[date, List[Dict]]:
    """
    Get detailed booking info per day for tooltips.
    
    Returns:
        Dictionary mapping dates to list of {client, venue} dicts
    """
    daily_details = defaultdict(list)
    
    for booking in bookings:
        date_obj = booking.get('date_obj')
        if isinstance(date_obj, datetime):
            daily_details[date_obj.date()].append({
                'client': booking.get('client_name', 'Unknown'),
                'venue': booking.get('venue', 'N/A')
            })
            
    return dict(daily_details)


def _find_top_item(items_map: Dict[str, int], default: str = "-") -> Tuple[str, int]:
    """
    Find the item with the highest count.
    
    Args:
        items_map: Dictionary mapping item names to counts
        default: Default name if map is empty
        
    Returns:
        Tuple of (top_item_name, count)
    """
    if not items_map:
        return (default, 0)
    
    try:
        top_item = max(items_map, key=items_map.get)
        return (top_item, items_map[top_item])
    except (ValueError, KeyError):
        return (default, 0)


# =============================================================================
# HELPER FUNCTIONS - Heatmap
# =============================================================================

def _calculate_color_intensity(count: int, max_count: int) -> str:
    """
    Calculate heatmap color based on event count.
    
    Args:
        count: Number of events
        max_count: Maximum events in dataset
        
    Returns:
        Hex color string
    """
    if count == 0 or max_count == 0:
        return HEATMAP_COLORS[0]
    
    try:
        # Map to 0-5 intensity levels
        intensity = min(5, int((count / max_count) * 5))
        return HEATMAP_COLORS[intensity]
    except (ZeroDivisionError, ValueError, TypeError):
        return HEATMAP_COLORS[0]


def _build_heatmap_cell(current_date: date, count: int, max_count: int) -> str:
    """
    Build HTML for a single heatmap cell.
    
    Args:
        current_date: Date for this cell
        count: Event count
        max_count: Maximum count for color scaling
        
    Returns:
        HTML string for the cell
    """
    bg_color = _calculate_color_intensity(count, max_count)
    tooltip = f"{current_date.strftime('%b %d')}: {count} event(s)"
    return f'<div class="cal-cell" style="background: {bg_color};" data-tooltip="{tooltip}"></div>'


# =============================================================================
# DATA LAYER - Cached Data Loading
# =============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_analytics_data(version_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch and process analytics data with comprehensive error handling & quality metrics.
    
    Returns:
        Dict with keys: 
        - 'bookings': List[Dict]
        - 'items': List[Dict]
        - 'meta': Dict (stats, indices)
    """
    try:
        raw_bookings = db.get_analytics_bookings(limit=2000)
        
        # Stats Init
        stats = {
            "total_loaded": 0,
            "skipped_rows": 0,
            "negative_sanitized": 0,
            "items_skipped": 0
        }
        
        # Pre-calc Indices
        unique_clients = set()
        unique_venues = set()
        year_month_index: Dict[Tuple[int, int], List[int]] = {} # (year, month) -> [indices]

        if not raw_bookings:
            return {"bookings": [], "items": [], "meta": stats}
        
        bookings: List[Dict] = []
        all_items: List[Dict] = []
        
        stats["total_loaded"] = len(raw_bookings)
        
        for raw in raw_bookings:
            try:
                # Safe date parsing
                d_obj = _parse_date_safe(raw.get('date'))
                if not d_obj:
                    stats["skipped_rows"] += 1
                    continue  # Skip invalid dates
                
                # Safe amount extraction with validation
                try:
                    amount = float(raw.get('amount', 0))
                    # Sanitize negative amounts
                    if amount < 0:
                        amount = 0.0
                        stats["negative_sanitized"] += 1
                except (ValueError, TypeError):
                    amount = 0.0
                
                # Build booking entry with safe defaults
                booking = {
                    'id': raw.get('id', 0),
                    'amount': amount,
                    'venue': raw.get('venue') or DEFAULT_VENUE,
                    'client_name': raw.get('client') or "Unknown",
                    'date_obj': d_obj,
                    'year': d_obj.year,
                    'month': d_obj.month,
                    'day': d_obj.day,
                    'month_name': d_obj.strftime('%B'),
                    'date_str': d_obj.strftime('%Y-%m-%d')
                }
                bookings.append(booking)
                
                # Update Indices
                c_name = booking['client_name']
                v_name = booking['venue']
                unique_clients.add(c_name)
                unique_venues.add(v_name)
                
                ym_key = (booking['year'], booking['month'])
                if ym_key not in year_month_index:
                    year_month_index[ym_key] = []
                # Store index of this booking in the main list
                year_month_index[ym_key].append(len(bookings) - 1)
                
                
                # Safe items processing
                raw_items = raw.get('items', [])
                if not isinstance(raw_items, list):
                    raw_items = []
                
                for item in raw_items:
                    if not isinstance(item, dict):
                        continue
                    
                    try:
                        qty = item.get('Qty', 1)
                        # Safe quantity conversion
                        if not isinstance(qty, (int, float)):
                            qty = 1
                        qty = max(0, int(qty))  # Ensure non-negative
                        
                        all_items.append({
                            'name': item.get('Description') or DEFAULT_PACKAGE,
                            'qty': qty,
                            'year': d_obj.year,
                            'month': d_obj.month
                        })
                    except Exception:
                        stats["items_skipped"] += 1
                        continue  # Skip invalid items
                        
            except Exception as e:
                # Log but don't crash
                stats["skipped_rows"] += 1
                # print(f"Warning: Skipping invalid booking {raw.get('id', '?')}: {e}")
                continue
        
        # Attach pre-calculated indices to meta
        stats["unique_clients"] = list(unique_clients)
        stats["unique_venues"] = list(unique_venues)
        # Convert tuple keys to string for JSON safety if needed, but dict is fine for internal use
        stats["year_month_index"] = year_month_index 
        
        return {
            "bookings": bookings, 
            "items": all_items, 
            "meta": stats
        }
        
    except Exception as e:
        print(f"Error loading analytics data: {e}")
        return [], []


# =============================================================================
# PDF HELPERS - Cached Report Generation
# =============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def _get_yearly_report_pdf(year: int) -> Optional[bytes]:
    """Generate yearly PDF report with error handling."""
    try:
        data = db.get_yearly_report_data(year)
        if not data:
            return None
            
        # Add visual insights
        chart_data = db.get_analytics_revenue_trend(year)
        
        return pdf_report.generate_yearly_report(data, year, chart_data=chart_data).getvalue()
    except Exception as e:
        # Cache-safe logging? No, but st.error works on first run
        # We print to console for cloud logs
        print(f"Error generating yearly report: {e}")
        return None


@st.cache_data(ttl=300, show_spinner=False)
def _get_monthly_report_pdf(year: int, month: int) -> Optional[bytes]:
    """Generate monthly PDF report with error handling."""
    try:
        data = db.get_monthly_report_data(year, month)
        if not data:
            return None
        return pdf_report.generate_monthly_report(data, year, month).getvalue()
    except Exception as e:
        print(f"Error generating monthly report: {e}")
        return None


# =============================================================================
# UI LAYER - Main Rendering Function
# =============================================================================

def render_page() -> None:
    """
    Render the analytics dashboard with professional error handling.
    """
    inject_styles()
    page_header("📊 Analytics Dashboard", "Business insights and performance metrics.")
    
    # 1. Load Data with error recovery
    try:
        # Panggil db.get_analytics_version() untuk cek versi data
        version_key = db.get_analytics_version()
    except Exception:
        version_key = None
        
    data_pkg = load_analytics_data(version_key=version_key)
    bookings = data_pkg.get("bookings", [])
    items = data_pkg.get("items", [])
    meta = data_pkg.get("meta", {})
    
    if not bookings:
        st.info("📭 No analytics data available yet. Create your first invoice to see insights!")
        return

    # --- Data Health Panel ---
    with st.expander("🛡 Data Health & Quality (Debug)", expanded=False):
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Total Loaded", meta.get("total_loaded", 0))
        d2.metric("Skipped Rows", meta.get("skipped_rows", 0), help="Invalid dates or corrupted rows")
        d3.metric("Negative Values Fix", meta.get("negative_sanitized", 0), help="Sanitized negative amounts")
        d4.metric("Items Skipped", meta.get("items_skipped", 0))
        
        st.caption(f"Unique Clients: {len(meta.get('unique_clients', []))} | Unique Venues: {len(meta.get('unique_venues', []))}")
    
    # 2. Global Context
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    try:
        current_target = float(db.get_config('monthly_target', '50000000'))
    except (ValueError, TypeError):
        current_target = 50000000.0
    
    # 3. Year Selection with Safe Defaults
    try:
        available_years = sorted(list(set(b['year'] for b in bookings if isinstance(b.get('year'), int))), reverse=True)
    except Exception:
        available_years = []
        
    if not available_years:
        available_years = [current_year]
    
    # =============================================================================
    # KPI CARDS LAYOUT - 2 ROW DESIGN FOR SYMMETRY
    # =============================================================================
    
    # ===== ROW 1: Yearly Overview + Monthly Detail (2 equal columns) =====
    k1, k2 = st.columns(2)
    
    # --- COLUMN 1: Yearly Overview ---
    with k1:
        with st.container(border=True):
            st.write("📅 **Yearly Overview**")
            
            selected_year = st.selectbox(
                "Select Year",
                options=available_years,
                index=0,
                label_visibility="collapsed",
                key="year_selector"
            )
            
            # Safe filtering
            bookings_curr = [b for b in bookings if b.get('year') == selected_year]
            bookings_prev = [b for b in bookings if b.get('year') == (selected_year - 1)]
            
            # Safe aggregation
            total_rev = sum(float(b.get('amount', 0)) for b in bookings_curr)
            prev_rev = sum(float(b.get('amount', 0)) for b in bookings_prev)
            
            # Safe growth calculation
            growth_html = ""
            if prev_rev > 0:
                try:
                    growth = ((total_rev - prev_rev) / prev_rev) * 100
                    color = "#166534" if growth >= 0 else "#dc2626"
                    icon = "⬆" if growth >= 0 else "⬇"
                    growth_text = f"{icon} {growth:.1f}% vs Last Year"
                    growth_html = f"<div style='color:{color}; font-size:0.8rem; margin-top:4px;'>{growth_text}</div>"
                except (ZeroDivisionError, ValueError):
                    growth_html = ""
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
            
            # PDF Download
            try:
                pdf_bytes = _get_yearly_report_pdf(selected_year)
                if pdf_bytes:
                    st.download_button(
                        "📥 Download Report",
                        data=pdf_bytes,
                        file_name=f"Report_{selected_year}.pdf",
                        mime='application/pdf',
                        key=f'yr_{selected_year}',
                        use_container_width=True
                    )
                else:
                    st.button("📥 No Data", disabled=True, use_container_width=True, key=f"no_yr_{selected_year}")
            except Exception as e:
                st.error(f"Generate Failed: {e}")
            
            st.markdown("<div style='height:4px; width:100%; background:#bbf7d0; margin-top:10px; border-radius:2px;'></div>", unsafe_allow_html=True)
    
    # --- COLUMN 2: Monthly Detail ---
    with k2:
        with st.container(border=True):
            st.write("🗓️ **Monthly Detail**")
            
            # Safe month selection
            current_month_idx = max(0, min(11, current_month - 1))
            selected_month = st.selectbox(
                "Select Month",
                options=range(1, 13),
                index=current_month_idx,
                format_func=lambda x: datetime(2000, x, 1).strftime('%B'),
                label_visibility="collapsed",
                key="month_selector"
            )
            
            month_name = datetime(2000, selected_month, 1).strftime('%B')
            
            # Safe monthly filtering
            bookings_mo = [b for b in bookings_curr if b.get('month') == selected_month]
            mo_rev = sum(float(b.get('amount', 0)) for b in bookings_mo)
            mo_count = len(bookings_mo)
            
            st.markdown(f"""
                <div style="margin-top: {CARD_PADDING};">
                    <div style="font-size: 0.85rem; color: #6b21a8; font-weight: 600;">Revenue ({month_name})</div>
                    <div style="font-size: 1.6rem; font-weight: 700; color: #7e22ce;">{rupiah(mo_rev)}</div>
                    <div style="font-size: 0.85rem; color: #a855f7; margin-top:4px;">{mo_count} Invoice{'' if mo_count == 1 else 's'}</div>
                </div>
            """, unsafe_allow_html=True)
            
            st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)
            
            try:
                pdf_bytes_mo = _get_monthly_report_pdf(selected_year, selected_month)
                if pdf_bytes_mo:
                    st.download_button(
                        "📥 Download Report",
                        data=pdf_bytes_mo,
                        file_name=f"Report_{selected_year}_{selected_month:02d}.pdf",
                        mime='application/pdf',
                        key=f'mo_{selected_year}_{selected_month}',
                        use_container_width=True
                    )
                else:
                    st.button("📥 No Data", disabled=True, use_container_width=True, key=f"no_mo_{selected_year}_{selected_month}")
            except Exception as e:
                st.error(f"Generate Failed: {e}")
            
            st.markdown("<div style='height:4px; width:100%; background:#e9d5ff; margin-top:10px; border-radius:2px;'></div>", unsafe_allow_html=True)
    
    # ===== ROW 2: Top Insights (Full Width - Horizontal Cards) =====
    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
    
    # Calculate insights values
    pct = (mo_rev / current_target * 100) if current_target > 0 else 0.0
    grow_col = "#16a34a" if pct >= 100 else "#dc2626"
    
    # Safe venue aggregation
    venue_map = defaultdict(int)
    for b in bookings_curr:
        venue = b.get('venue', DEFAULT_VENUE)
        if venue:
            venue_map[venue] += 1
    top_venue, top_venue_cnt = _find_top_item(dict(venue_map), DEFAULT_VENUE)
    
    # Safe package aggregation
    pkg_map = defaultdict(int)
    for item in items:
        if item.get('year') == selected_year:
            name = item.get('name', DEFAULT_PACKAGE)
            qty = item.get('qty', 0)
            if name and isinstance(qty, (int, float)):
                pkg_map[name] += int(qty)
    top_pkg, top_pkg_cnt = _find_top_item(dict(pkg_map), DEFAULT_PACKAGE)
    
    # Calculate Top Month
    monthly_rev = defaultdict(float)
    for b in bookings_curr:
        monthly_rev[b.get('month_name', 'Unknown')] += b.get('amount', 0)
    top_month, top_month_rev = _find_top_item(dict(monthly_rev), "-")
    
    total_invoices = len(bookings_curr)
    
    # Top Insights - Full Width Container
    with st.container(border=True):
        st.write("🏆 **Top Insights**")
        
        # 6 columns for horizontal layout
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        
        with c1:
            st.markdown(f"""<div style="padding:8px; background:#eff6ff; border-radius:6px; text-align:center;">
<div style="font-size:0.65rem; color:#1e40af; font-weight:600; text-transform:uppercase;">Target ({month_name})</div>
<div style="font-size:1rem; font-weight:700; color:#1d4ed8; margin-top:4px;">{rupiah(mo_rev)}</div>
<div style="font-size:0.65rem; color:#60a5fa;">of {rupiah(current_target)}</div>
</div>""", unsafe_allow_html=True)
        
        with c2:
            st.markdown(f"""<div style="padding:8px; background:#eff6ff; border-radius:6px; text-align:center;">
<div style="font-size:0.65rem; color:#1e40af; font-weight:600; text-transform:uppercase;">Status ({month_name})</div>
<div style="font-size:1rem; font-weight:700; color:{grow_col}; margin-top:4px;">{pct:.1f}%</div>
<div style="font-size:0.65rem; color:#94a3b8;">Achieved</div>
</div>""", unsafe_allow_html=True)
        
        with c3:
            st.markdown(f"""<div style="padding:8px; background:#eff6ff; border-radius:6px; text-align:center;">
<div style="font-size:0.65rem; color:#1e40af; font-weight:600; text-transform:uppercase;">Top Month</div>
<div style="font-size:0.9rem; font-weight:700; color:#1d4ed8; margin-top:4px;">{top_month}</div>
<div style="font-size:0.65rem; color:#60a5fa;">{rupiah(top_month_rev)}</div>
</div>""", unsafe_allow_html=True)
        
        with c4:
            st.markdown(f"""<div style="padding:8px; background:#eff6ff; border-radius:6px; text-align:center;">
<div style="font-size:0.65rem; color:#1e40af; font-weight:600; text-transform:uppercase;">Total Invoices</div>
<div style="font-size:1rem; font-weight:700; color:#1d4ed8; margin-top:4px;">{total_invoices}</div>
<div style="font-size:0.65rem; color:#60a5fa;">this year</div>
</div>""", unsafe_allow_html=True)
        
        with c5:
            st.markdown(f"""<div style="padding:8px; background:#eff6ff; border-radius:6px; text-align:center;">
<div style="font-size:0.65rem; color:#1e40af; font-weight:600; text-transform:uppercase;">Top Venue</div>
<div style="font-size:0.85rem; font-weight:700; color:#1d4ed8; margin-top:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{top_venue}</div>
<div style="font-size:0.65rem; color:#60a5fa;">{top_venue_cnt} Event{'' if top_venue_cnt == 1 else 's'}</div>
</div>""", unsafe_allow_html=True)
        
        with c6:
            st.markdown(f"""<div style="padding:8px; background:#eff6ff; border-radius:6px; text-align:center;">
<div style="font-size:0.65rem; color:#1e40af; font-weight:600; text-transform:uppercase;">Top Package</div>
<div style="font-size:0.85rem; font-weight:700; color:#1d4ed8; margin-top:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{top_pkg}</div>
<div style="font-size:0.65rem; color:#60a5fa;">{top_pkg_cnt} Sold</div>
</div>""", unsafe_allow_html=True)
        
        st.markdown("<div style='height:4px; width:100%; background:#bfdbfe; margin-top:10px; border-radius:2px;'></div>", unsafe_allow_html=True)
    
    # =============================================================================
    # CHARTS SECTION
    # =============================================================================
    
    st.write("")
    st.markdown(f"<div style='margin-top: {SECTION_GAP};'></div>", unsafe_allow_html=True)
    
    st.subheader(f"📈 Revenue Trends ({selected_year})")
    
    # Target Settings (MOVED TO TOP)
    with st.expander("🎯 Target Settings", expanded=False):
        col_t1, col_t2 = st.columns([1, 2])
        with col_t1:
            try:
                new_target = st.number_input(
                    "Monthly Revenue Target (Rp)",
                    min_value=0.0,
                    value=current_target,
                    step=1000000.0,
                    key="target_input"
                )
                if new_target != current_target:
                    db.set_config('monthly_target', str(new_target))
                    st.rerun()
            except Exception as e:
                st.error(f"Error updating target: {e}")
        with col_t2:
            # Show current progress
            pct_achieved = (mo_rev / current_target * 100) if current_target > 0 else 0
            status_emoji = "✅" if pct_achieved >= 100 else "📊"
            st.caption(f"**Current Progress:** {rupiah(mo_rev)} / {rupiah(current_target)} ({pct_achieved:.1f}%) {status_emoji}")
    
    # Prepare monthly data as list of dicts (Altair accepts this directly - NO PANDAS!)
    monthly_dict = _aggregate_monthly_data(bookings, selected_year)
    chart_data = [{'month': month, 'amount': amount} for month, amount in monthly_dict.items()]
    
    # Render Altair chart with target line
    try:
        # Bar chart
        bars = alt.Chart(alt.Data(values=chart_data)).mark_bar(
            cornerRadiusTopLeft=4,
            cornerRadiusTopRight=4,
            color='#10b981'
        ).encode(
            x=alt.X('month:N', sort=None, axis=alt.Axis(labelAngle=0, title=None, grid=False)),
            y=alt.Y('amount:Q', axis=alt.Axis(format=',.0f', title=None, grid=True, tickCount=5)),
            tooltip=[
                alt.Tooltip('month:N', title='Bulan'),
                alt.Tooltip('amount:Q', format=',.0f', title='Pendapatan')
            ]
        )
        
        # Target line (red dashed) - reactive & attached to chart!
        if current_target > 0:
            target_data = alt.Data(values=[{'target': current_target}])
            target_line = alt.Chart(target_data).mark_rule(
                color='#ef4444',
                strokeDash=[8, 4],
                strokeWidth=2
            ).encode(
                y='target:Q',
                tooltip=[alt.Tooltip('target:Q', format=',.0f', title='🎯 Target')]
            )
            chart = (bars + target_line).properties(height=300)
        else:
            chart = bars.properties(height=300)
        
        st.altair_chart(chart, use_container_width=True)
        
    except Exception as e:
        st.error(f"Error rendering chart: {e}")
    
    # =============================================================================
    # EVENT CALENDAR - MONTHLY GRID VIEW
    # =============================================================================
    
    st.markdown(f"<div style='margin-top: {SECTION_GAP};'></div>", unsafe_allow_html=True)
    
    # Header & Toggle Row
    cc1, cc2 = st.columns([2, 1])
    with cc1:
        st.subheader(f"📅 Event Calendar ({selected_year})")
    with cc2:
        show_full_year = st.toggle("Show Full Year", value=False, help="Toggle to show all 12 months or just current active months")
    
    daily_counts = _aggregate_daily_data(bookings_curr)
    daily_details = _aggregate_daily_details(bookings_curr)  # For rich tooltips
    
    if not daily_counts:
        st.info("📭 No events scheduled for this year yet.")
    else:
        try:
            import calendar as cal
            
            max_count = max(daily_counts.values()) if daily_counts.values() else 1
            
            # Color gradient (purple/blue theme)
            def get_cell_color(count, max_val):
                if count == 0:
                    return "#f8fafc"  # Light gray
                ratio = count / max(1, max_val)
                if ratio <= 0.25:
                    return "#d1fae5"  # Light green
                elif ratio <= 0.5:
                    return "#6ee7b7"  # Medium green
                elif ratio <= 0.75:
                    return "#34d399"  # Green
                else:
                    return "#10b981"  # Dark green
            
            # Inject custom tooltip CSS (prettier than native title)
            st.markdown("""<style>
.cal-day{position:relative;transition:transform 0.15s ease;}
.cal-day:hover{transform:scale(1.2);z-index:100;}
.cal-day .tooltip{visibility:hidden;opacity:0;position:absolute;bottom:130%;left:50%;transform:translateX(-50%);background:#1f2937;color:#fff;padding:8px 12px;border-radius:6px;font-size:11px;white-space:pre-line;min-width:140px;max-width:200px;box-shadow:0 4px 12px rgba(0,0,0,0.2);z-index:1000;transition:opacity 0.2s ease;}
.cal-day .tooltip::after{content:'';position:absolute;top:100%;left:50%;transform:translateX(-50%);border:6px solid transparent;border-top-color:#1f2937;}
.cal-day:hover .tooltip{visibility:visible;opacity:1;}
</style>""", unsafe_allow_html=True)
            
            # --- RENDER CALENDAR GRID ---
            # Use CSS Grid for flexible layout (responsive) instead of fixed st.columns
            st.markdown('<div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(250px, 1fr));gap:16px;">', unsafe_allow_html=True)
            
            # Determine range
            months_to_render = []
            if show_full_year:
                months_to_render = list(range(1, 13))
            else:
                # Optimized Logic:
                # 1. Always show months that have data
                months_with_data = set(d.get('month') for d in bookings_curr if d.get('month'))
                
                # 2. If current year, ALSO show current month + next month (for planning)
                now = datetime.now()
                if selected_year == now.year:
                    months_with_data.add(now.month)
                    if now.month < 12:
                        months_with_data.add(now.month + 1)
                
                # 3. If no data and no current context, default to Jan
                if not months_with_data:
                    months_to_render = [1]
                else:
                    months_to_render = sorted(list(months_with_data))
            
            # Render selected months
            for month_num in months_to_render:
                with st.container(): # Container for streamlits purposes, but we wrap in HTML div
                    month_name = date(selected_year, month_num, 1).strftime('%B')
                    month_cal = cal.monthcalendar(selected_year, month_num)
                    
                    # Wrap each month in a div that matches the grid
                    # We need to close the grid at the end, so we can't easily mix st.write and raw HTML grid here
                    # Strategy: Generating HTML for ALL selected months and rendering ONCE is fastest.
                    pass 

            # RE-STRATEGY: Streamlit containers break inside HTML grids. 
            # We must use st.columns if we want native feel, or pure HTML.
            # Let's use logic to render in chunks of 4 if doing full year, or flow if partial.

            # Actual Implementation:
            cols = st.columns(4) # Standard grid
            
            # If optimized (few months), use fewer columns or just flow
            if len(months_to_render) < 4:
                cols = st.columns(len(months_to_render))

            for i, month_num in enumerate(months_to_render):
                col_idx = i % 4
                if len(months_to_render) < 4:
                    col_idx = i
                elif i > 0 and i % 4 == 0:
                    cols = st.columns(4) # New row

                with cols[col_idx]:
                    month_name = date(selected_year, month_num, 1).strftime('%B')
                    month_cal = cal.monthcalendar(selected_year, month_num)
                        
                    # Build HTML for this month
                    html = f'<div style="border:1px solid #e5e7eb;border-radius:8px;padding:12px;background:white;margin-bottom:12px;height:100%;">'
                    html += f'<div style="font-weight:600;color:#166534;margin-bottom:8px;font-size:0.85rem;text-align:center;">{month_name}</div>' 
                    
                    # Insert headers
                    html += '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px;margin-bottom:6px;">'
                    for day_name in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]:
                        html += f'<div style="text-align:center;font-size:0.65rem;color:#9ca3af;font-weight:600;">{day_name}</div>'
                    html += '</div>'
                    
                    # Insert days
                    html += '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px;">'
                    for week in month_cal:
                        for day in week:
                            if day == 0:
                                html += '<div style="width:24px;height:24px;"></div>'
                            else:
                                day_date = date(selected_year, month_num, day)
                                count = daily_counts.get(day_date, 0)
                                details = daily_details.get(day_date, [])
                                
                                # Color Logic
                                max_val = max(1, max_count)
                                bg = "#f8fafc" # default
                                tc = "#94a3b8" # default text
                                if count > 0:
                                    ratio = count / max_val
                                    if ratio <= 0.25: bg = "#d1fae5" 
                                    elif ratio <= 0.5: bg = "#6ee7b7"
                                    elif ratio <= 0.75: bg = "#34d399"
                                    else: bg = "#10b981"
                                    tc = "#fff"
                                
                                # Tooltip Logic
                                if count == 0:
                                    tt_content = f"📅 {day_date.strftime('%b %d')}<br>No events"
                                else:
                                    tt_content = f"📅 <b>{day_date.strftime('%b %d')}</b><br>{count} event(s)<br>"
                                    for evt in details[:3]:
                                        tt_content += f"• {evt['client']} @ {evt['venue']}<br>"
                                    if len(details) > 3:
                                        tt_content += f"<i>+{len(details)-3} more...</i>"
                                
                                # Render Cell - Single line to avoid Markdown code block interpretation
                                html += f'<div class="cal-day" style="width:24px;height:24px;background:{bg};border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:0.65rem;font-weight:600;color:{tc};cursor:pointer;">'
                                html += f'<div class="tooltip">{tt_content}</div>{day}</div>'
                    html += '</div></div>'
                    st.markdown(html, unsafe_allow_html=True)

            # End of loop logic replacing the hardcoded ranges
            pass
                        

            
            # Legend (Green Theme)
            st.markdown("""<div style="display:flex;align-items:center;gap:10px;margin-top:10px;font-size:0.75rem;color:#6b7280;justify-content:center;"><span>Less</span><div style="width:18px;height:18px;background:#f3f4f6;border-radius:4px;border:1px solid #e5e7eb;"></div><div style="width:18px;height:18px;background:#d1fae5;border-radius:4px;"></div><div style="width:18px;height:18px;background:#6ee7b7;border-radius:4px;"></div><div style="width:18px;height:18px;background:#34d399;border-radius:4px;"></div><div style="width:18px;height:18px;background:#10b981;border-radius:4px;"></div><span>More</span></div>""", unsafe_allow_html=True)
            
            # --- QUICK EVENT NAVIGATOR ---
            # Bridge the gap between visual calendar and editing
            st.markdown(f"<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
            
            if bookings_curr:
                with st.container(border=True):
                    st.caption("🚀 **Quick Jump to Event**")
                    
                    # Month Filter + Event Selector
                    c_month, c_evt, c_btn = st.columns([1, 2.5, 1], vertical_alignment="bottom")
                    
                    with c_month:
                        # Get unique months from data
                        months_in_data = sorted(list(set(b['month'] for b in bookings_curr)))
                        month_options = [date(2000, m, 1).strftime("%B") for m in months_in_data]
                        
                        selected_month_name = st.selectbox(
                            "Filter Month", 
                            options=month_options, 
                            index=0, 
                            key="qj_month_filter",
                            label_visibility="collapsed"
                        )
                    
                    with c_evt:
                        # Filter events by selected month
                        # Convert month name back to number
                        month_num = datetime.strptime(selected_month_name, "%B").month
                        filtered_evts = [b for b in bookings_curr if b['month'] == month_num]
                        
                        # Sort by date
                        sorted_evts = sorted(filtered_evts, key=lambda x: x['date_str'])
                        
                        if not sorted_evts:
                            st.info("No events in this month.")
                            selected_evt_id = None
                        else:
                            selected_evt_id = st.selectbox(
                                "Select Event",
                                options=[b['id'] for b in sorted_evts],
                                format_func=lambda x: next((f"📅 {b['date_str']} | {b['client_name']} @ {b['venue']}" for b in sorted_evts if b['id'] == x), "Unknown"),
                                key="quick_nav_evt",
                                label_visibility="collapsed"
                            )
                    
                    with c_btn:
                        if st.button("✏️ Edit Invoice", use_container_width=True, type="primary"):
                            if selected_evt_id:
                                # Robust Edit Logic (Copied from history_view behavior)
                                try:
                                    detail = db.get_invoice_details(selected_evt_id)
                                    if detail:
                                        payload = json.loads(detail["invoice_data"])
                                        meta = payload.get("meta", {})
                                        
                                        # Restore State
                                        st.session_state["inv_items"] = payload.get("items", [])
                                        st.session_state["inv_no"] = meta.get("inv_no", "")
                                        st.session_state["inv_title"] = meta.get("title", "")
                                        st.session_state["inv_client_name"] = meta.get("client_name", "")
                                        st.session_state["inv_client_phone"] = meta.get("client_phone", "")
                                        st.session_state["inv_client_email"] = meta.get("client_email", "")
                                        st.session_state["inv_venue"] = meta.get("venue", "")
                                        
                                        # Date Parsing
                                        w_date_str = meta.get("wedding_date", "")
                                        if w_date_str:
                                            try:
                                                import locale
                                                # Try force English for parsing
                                                try:
                                                    saved = locale.getlocale(locale.LC_TIME)
                                                    locale.setlocale(locale.LC_TIME, 'C')
                                                except: saved = None
                                                
                                                parsed = None
                                                for fmt in ["%A, %d %B %Y", "%d %B %Y", "%Y-%m-%d"]:
                                                    try:
                                                        parsed = datetime.strptime(w_date_str, fmt).date()
                                                        break
                                                    except: continue
                                                if parsed:
                                                    st.session_state["inv_wedding_date"] = parsed
                                                
                                                if saved:
                                                    try: locale.setlocale(locale.LC_TIME, saved)
                                                    except: pass
                                            except: pass
                                            
                                        st.session_state["inv_cashback"] = float(meta.get("cashback", 0))
                                        
                                        # Payment Terms
                                        pt = meta.get("payment_terms")
                                        if pt:
                                            st.session_state["payment_terms"] = pt
                                        else:
                                            # Fail-safe empty
                                            st.session_state["payment_terms"] = []
                                            
                                        st.session_state["inv_terms"] = meta.get("terms", "")
                                        st.session_state["bank_nm"] = meta.get("bank_name", "")
                                        st.session_state["bank_ac"] = meta.get("bank_acc", "")
                                        st.session_state["bank_an"] = meta.get("bank_holder", "")
                                        
                                        pp = meta.get("payment_proof")
                                        st.session_state["pp_cached"] = [pp] if pp and not isinstance(pp, list) else (pp or [])
                                        
                                        # Set Edit Mode
                                        st.session_state["editing_invoice_id"] = selected_evt_id
                                        st.session_state["menu_selection"] = "🧾 Create Invoice"
                                        st.session_state["nav_key"] = st.session_state.get("nav_key", 0) + 1
                                        st.rerun()
                                    else:
                                        st.error("Invoice data not found.")
                                except Exception as e:
                                    st.error(f"Failed to load invoice: {e}")

        except Exception as e:
            st.error(f"Error rendering calendar: {e}")
