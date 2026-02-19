"""
Analytics Aggregation Layer — Pure functions for computing KPIs, trends, calendar data.
No Streamlit dependency, no side effects.
"""
from datetime import datetime, date
from typing import List, Dict, Tuple, Any
from collections import defaultdict


def aggregate_monthly_data(bookings: List[Dict], year: int) -> Dict[str, float]:
    """Aggregate booking amounts by month for a specific year."""
    monthly = {datetime(2000, m, 1).strftime("%b"): 0.0 for m in range(1, 13)}

    for b in bookings:
        if b.get("year") == year:
            month_key = b.get("month_name", "")[:3]
            if month_key in monthly:
                try:
                    monthly[month_key] += max(0.0, float(b.get("amount", 0)))
                except (ValueError, TypeError):
                    pass

    return {k: max(0.0, v) for k, v in monthly.items()}


def aggregate_daily_data(bookings: List[Dict]) -> Dict[date, int]:
    """Count bookings per day."""
    counts: Dict[date, int] = defaultdict(int)
    for b in bookings:
        d = b.get("date_obj")
        if isinstance(d, datetime):
            counts[d.date()] += 1
    return dict(counts)


def aggregate_daily_details(bookings: List[Dict]) -> Dict[date, List[Dict]]:
    """Get detailed booking info per day (for tooltips)."""
    details: Dict[date, List[Dict]] = defaultdict(list)
    for b in bookings:
        d = b.get("date_obj")
        if isinstance(d, datetime):
            details[d.date()].append({
                "client": b.get("client_name", "Unknown"),
                "venue": b.get("venue", "N/A"),
            })
    return dict(details)


def find_top_item(items_map: Dict[str, Any], default: str = "-") -> Tuple[str, Any]:
    """Find the item with the highest value in a dict."""
    if not items_map:
        return (default, 0)
    try:
        top = max(items_map, key=items_map.get)
        return (top, items_map[top])
    except (ValueError, KeyError):
        return (default, 0)


def compute_kpi_data(
    bookings: List[Dict],
    items: List[Dict],
    selected_year: int,
    selected_month: int,
    current_target: float,
) -> Dict[str, Any]:
    """
    Pre-compute all KPI values needed by the UI layer.
    Returns a flat dict with all computed metrics.
    """
    bookings_curr = [b for b in bookings if b.get("year") == selected_year]
    bookings_prev = [b for b in bookings if b.get("year") == (selected_year - 1)]
    bookings_month = [b for b in bookings_curr if b.get("month") == selected_month]

    total_rev = sum(float(b.get("amount") or 0) for b in bookings_curr)
    prev_rev = sum(float(b.get("amount") or 0) for b in bookings_prev)
    mo_rev = sum(float(b.get("amount") or 0) for b in bookings_month)
    mo_count = len(bookings_month)

    # Growth
    if prev_rev > 0:
        try:
            growth = ((total_rev - prev_rev) / prev_rev) * 100
        except ZeroDivisionError:
            growth = None
    else:
        growth = None

    # Target
    pct = (mo_rev / current_target * 100) if current_target > 0 else 0.0

    # Top venue (this year)
    venue_map: Dict[str, int] = defaultdict(int)
    for b in bookings_curr:
        v = b.get("venue", "Unknown")
        if v:
            venue_map[v] += 1
    top_venue, top_venue_cnt = find_top_item(dict(venue_map), "Unknown")

    # Top package (this year)
    pkg_map: Dict[str, int] = defaultdict(int)
    for item in items:
        if item.get("year") == selected_year:
            name = item.get("name", "Unknown")
            qty = item.get("qty", 0)
            if name and isinstance(qty, (int, float)):
                pkg_map[name] += int(qty)
    top_pkg, top_pkg_cnt = find_top_item(dict(pkg_map), "Unknown")

    # Top month (this year)
    monthly_rev: Dict[str, float] = defaultdict(float)
    for b in bookings_curr:
        monthly_rev[b.get("month_name", "Unknown")] += float(b.get("amount") or 0)
    top_month, top_month_rev = find_top_item(dict(monthly_rev), "-")

    return {
        "bookings_curr": bookings_curr,
        "bookings_prev": bookings_prev,
        "bookings_month": bookings_month,
        "total_rev": total_rev,
        "prev_rev": prev_rev,
        "mo_rev": mo_rev,
        "mo_count": mo_count,
        "growth": growth,
        "pct": pct,
        "top_venue": top_venue,
        "top_venue_cnt": top_venue_cnt,
        "top_pkg": top_pkg,
        "top_pkg_cnt": top_pkg_cnt,
        "top_month": top_month,
        "top_month_rev": top_month_rev,
        "total_invoices": len(bookings_curr),
    }
