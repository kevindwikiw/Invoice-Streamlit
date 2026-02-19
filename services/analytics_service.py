"""
Analytics Service Layer — Data Loading, Normalization, Types.
Production-grade: no locale dependency, cloud-safe caching.
"""
import streamlit as st
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any, TypedDict
from modules import db


# =============================================================================
# TYPE DEFINITIONS
# =============================================================================

class BookingRecord(TypedDict):
    id: int
    amount: float
    venue: str
    client_name: str
    date_obj: datetime
    year: int
    month: int
    day: int
    month_name: str
    date_str: str


class ItemRecord(TypedDict):
    name: str
    qty: int
    year: int
    month: int


class AnalyticsData(TypedDict):
    bookings: List[BookingRecord]
    items: List[ItemRecord]
    meta: Dict[str, Any]


# =============================================================================
# CONSTANTS
# =============================================================================

DEFAULT_VENUE = "Unknown"
DEFAULT_PACKAGE = "Unknown"

# Unified heatmap color palette (green theme)
_HEATMAP_THRESHOLDS = [
    (0.00, "#f8fafc"),   # No events
    (0.01, "#d1fae5"),   # Light green
    (0.25, "#6ee7b7"),   # Medium green
    (0.50, "#34d399"),   # Green
    (0.75, "#10b981"),   # Dark green
]


# =============================================================================
# DATE PARSING — No locale dependency
# =============================================================================

_DATE_FORMATS = (
    "%A, %d %B %Y",    # Sunday, 12 January 2025
    "%d %B %Y",         # 12 January 2025
    "%B %Y",            # January 2025
    "%Y-%m-%d",         # 2025-01-12
    "%Y-%m-%d %H:%M:%S",  # 2025-01-12 15:30:00
    "%d-%m-%Y",         # 12-01-2025
)


def parse_date_safe(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse a date string using multiple format fallbacks.
    No locale dependency — works on any cloud environment.
    """
    if not date_str or not isinstance(date_str, str):
        return None

    cleaned = date_str.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except (ValueError, TypeError):
            continue

    # ISO fallback
    try:
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError):
        return None


# =============================================================================
# COLOR HELPER — Single unified function
# =============================================================================

def get_cell_color(count: int, max_val: int) -> str:
    """Get heatmap cell color based on event count ratio."""
    if count == 0 or max_val == 0:
        return _HEATMAP_THRESHOLDS[0][1]

    ratio = count / max(1, max_val)
    result = _HEATMAP_THRESHOLDS[0][1]
    for threshold, color in _HEATMAP_THRESHOLDS:
        if ratio >= threshold:
            result = color
    return result


# =============================================================================
# DATA LOADING — Cached, cloud-safe
# =============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_analytics_data(_version_key: Optional[str] = None) -> AnalyticsData:
    """
    Fetch and normalize all analytics data.
    
    Args:
        _version_key: Cache-busting key (prefixed with _ so Streamlit skips hashing)
    
    Returns:
        AnalyticsData with bookings, items, and meta stats
    """
    stats: Dict[str, Any] = {
        "total_loaded": 0,
        "skipped_rows": 0,
        "negative_sanitized": 0,
        "items_skipped": 0,
    }

    try:
        raw_bookings = db.get_analytics_bookings(limit=2000)
    except Exception as e:
        print(f"[Analytics] DB fetch failed: {e}")
        return {"bookings": [], "items": [], "meta": {"error": str(e)}}

    if not raw_bookings:
        return {"bookings": [], "items": [], "meta": stats}

    stats["total_loaded"] = len(raw_bookings)
    
    bookings: List[BookingRecord] = []
    all_items: List[ItemRecord] = []
    unique_clients: set = set()
    unique_venues: set = set()
    year_month_index: Dict[Tuple[int, int], List[int]] = {}

    for raw in raw_bookings:
        try:
            d_obj = parse_date_safe(raw.get("date"))
            if not d_obj:
                stats["skipped_rows"] += 1
                continue

            # Safe amount
            try:
                amount = max(0.0, float(raw.get("amount", 0)))
            except (ValueError, TypeError):
                amount = 0.0
                stats["negative_sanitized"] += 1

            booking: BookingRecord = {
                "id": raw.get("id", 0),
                "amount": amount,
                "venue": raw.get("venue") or DEFAULT_VENUE,
                "client_name": raw.get("client") or "Unknown",
                "date_obj": d_obj,
                "year": d_obj.year,
                "month": d_obj.month,
                "day": d_obj.day,
                "month_name": d_obj.strftime("%B"),
                "date_str": d_obj.strftime("%Y-%m-%d"),
            }
            bookings.append(booking)

            unique_clients.add(booking["client_name"])
            unique_venues.add(booking["venue"])

            ym_key = (booking["year"], booking["month"])
            year_month_index.setdefault(ym_key, []).append(len(bookings) - 1)

            # Items
            raw_items = raw.get("items", [])
            if not isinstance(raw_items, list):
                raw_items = []

            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                try:
                    qty = item.get("Qty", 1)
                    if not isinstance(qty, (int, float)):
                        qty = 1
                    qty = max(0, int(qty))

                    all_items.append({
                        "name": item.get("Description") or DEFAULT_PACKAGE,
                        "qty": qty,
                        "year": d_obj.year,
                        "month": d_obj.month,
                    })
                except Exception:
                    stats["items_skipped"] += 1

        except Exception:
            stats["skipped_rows"] += 1

    stats["unique_clients"] = list(unique_clients)
    stats["unique_venues"] = list(unique_venues)
    stats["year_month_index"] = year_month_index

    return {"bookings": bookings, "items": all_items, "meta": stats}
