from datetime import datetime, timedelta
from typing import Optional, List
import re

# Asia/Jakarta VTIMEZONE block (WIB +0700, no DST)
VTIMEZONE_JAKARTA = (
    "BEGIN:VTIMEZONE\r\n"
    "TZID:Asia/Jakarta\r\n"
    "BEGIN:STANDARD\r\n"
    "DTSTART:19700101T000000\r\n"
    "TZOFFSETFROM:+0700\r\n"
    "TZOFFSETTO:+0700\r\n"
    "TZNAME:WIB\r\n"
    "END:STANDARD\r\n"
    "END:VTIMEZONE"
)


def _parse_event_date(date_str: str) -> Optional[datetime]:
    """Parse event date string to datetime with broad format support."""
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip()
    for fmt in ("%A, %d %B %Y", "%d %B %Y", "%B %Y", "%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt)
        except (ValueError, TypeError):
            continue
    try:
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        pass
    return None


def _parse_event_time(time_str: str):
    """Parse time range string like '08:00 AM - 02:00 PM' to (start_time, end_time)."""
    if not time_str or "-" not in time_str:
        return None, None
    try:
        parts = time_str.split("-")
        t1 = datetime.strptime(parts[0].strip(), "%I:%M %p")
        t2 = datetime.strptime(parts[1].strip(), "%I:%M %p")
        return t1.time(), t2.time()
    except (ValueError, TypeError, IndexError):
        return None, None


def _escape_ics(text: str) -> str:
    """Escape special characters for ICS format."""
    if not text:
        return ""
    text = text.replace("\\", "\\\\")
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    text = text.replace("\n", "\\n")
    return text


def _sanitize_uid(text: str) -> str:
    """Sanitize UID: replace spaces and special chars."""
    return re.sub(r'[^A-Za-z0-9_\-@.]', '_', text)


def _fmt_currency(amount) -> str:
    """Format amount as Rp string."""
    try:
        return f"Rp {int(float(amount)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "Rp 0"


def _get_payment_status(payment_terms) -> str:
    """Determine payment status from payment terms."""
    if not payment_terms or not isinstance(payment_terms, list):
        return "UNPAID"
    try:
        pelunasan = next((t for t in payment_terms if t.get("id") == "full"), None)
        if pelunasan and int(float(pelunasan.get("amount", 0))) > 0:
            return "LUNAS"
        if any(int(float(t.get("amount", 0))) > 0 for t in payment_terms if t.get("id") != "full"):
            return "DP"
    except (ValueError, TypeError):
        pass
    return "UNPAID"


def _build_event_lines(meta: dict, grand_total: float, now_str: str) -> Optional[List[str]]:
    """Build VEVENT lines from invoice meta. Returns None if no valid date."""
    event_date = _parse_event_date(meta.get("wedding_date", ""))
    if not event_date:
        return None

    client_name = meta.get("client_name", "Client")
    event_title = meta.get("title", "")
    summary = f"{client_name} ({event_title})" if event_title else client_name

    location = meta.get("venue", "")
    hours_str = meta.get("hours", "")
    start_time, end_time = _parse_event_time(hours_str)
    has_time = start_time is not None and end_time is not None

    inv_no = meta.get("inv_no", "-")
    uid = _sanitize_uid(f"{inv_no}-{event_date.strftime('%Y%m%d')}@orbitphoto")

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now_str}",
        f"SUMMARY:{_escape_ics(summary)}",
    ]

    if has_time:
        dt_start = event_date.replace(hour=start_time.hour, minute=start_time.minute)
        dt_end = event_date.replace(hour=end_time.hour, minute=end_time.minute)
        if dt_end <= dt_start:
            dt_end += timedelta(days=1)
        dt_travel = dt_start - timedelta(hours=2)

        # Use TZID=Asia/Jakarta for proper timezone
        lines.append(f"DTSTART;TZID=Asia/Jakarta:{dt_start.strftime('%Y%m%dT%H%M%S')}")
        lines.append(f"DTEND;TZID=Asia/Jakarta:{dt_end.strftime('%Y%m%dT%H%M%S')}")
        lines.append("X-APPLE-TRAVEL-DURATION:PT2H0M")
        lines.append(f"X-APPLE-TRAVEL-START;TZID=Asia/Jakarta:{dt_travel.strftime('%Y%m%dT%H%M%S')}")
    else:
        lines.append(f"DTSTART;VALUE=DATE:{event_date.strftime('%Y%m%d')}")
        lines.append(f"DTEND;VALUE=DATE:{(event_date + timedelta(days=1)).strftime('%Y%m%d')}")

    if location:
        lines.append(f"LOCATION:{_escape_ics(location)}")

    # Notes
    status = _get_payment_status(meta.get("payment_terms", []))
    notes_parts = [
        f"Invoice: {inv_no}",
        f"Status: {status}",
        f"Event Date: {meta.get('wedding_date', '-')}",
        f"Amount: {_fmt_currency(grand_total)}",
    ]
    if hours_str:
        notes_parts.append(f"Hours: {hours_str}")
    lines.append(f"DESCRIPTION:{_escape_ics(chr(10).join(notes_parts))}")

    # Alerts
    lines.extend([
        "BEGIN:VALARM", "TRIGGER:-P1D", "ACTION:DISPLAY",
        f"DESCRIPTION:Event tomorrow: {_escape_ics(summary)}",
        "END:VALARM",
        "BEGIN:VALARM", "TRIGGER:-P4D", "ACTION:DISPLAY",
        f"DESCRIPTION:Event in 4 days: {_escape_ics(summary)}",
        "END:VALARM",
    ])

    lines.append("STATUS:CONFIRMED")
    lines.append("END:VEVENT")
    return lines


def generate_ics(meta: dict, grand_total: float = 0) -> Optional[str]:
    """Generate a single-event ICS file from invoice metadata."""
    now_str = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    event_lines = _build_event_lines(meta, grand_total, now_str)
    if not event_lines:
        return None

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//OrbitPhoto//InvoiceApp//EN",
        "CALSCALE:GREGORIAN",
        VTIMEZONE_JAKARTA,
    ]
    lines.extend(event_lines)
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def generate_subscription_ics(events: List[dict]) -> str:
    """Generate a combined ICS calendar with ALL events for subscription/batch import."""
    now_str = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//OrbitPhoto//InvoiceApp//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:Orbit Photo Events",
        "X-WR-CALDESC:All scheduled photography events",
        "X-WR-TIMEZONE:Asia/Jakarta",
        VTIMEZONE_JAKARTA,
    ]

    for evt in events:
        meta = evt.get("meta", {})
        grand_total = evt.get("grand_total", 0)
        event_lines = _build_event_lines(meta, grand_total, now_str)
        if event_lines:
            lines.extend(event_lines)

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def regenerate_static_calendar():
    """
    Regenerate the static calendar.ics file for subscription.
    Called after every invoice save/update/delete.
    The file is served at: https://<host>/static/calendar.ics
    """
    import os
    import json

    try:
        from modules import db

        # Ensure static directory exists
        static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
        os.makedirs(static_dir, exist_ok=True)

        # Fetch all invoices
        all_invs = db.get_invoices(limit=2000)
        events = []
        for inv in all_invs:
            try:
                detail = db.get_invoice_details(inv["id"])
                if detail:
                    raw = detail.get("invoice_data", "{}")
                    payload = json.loads(raw) if isinstance(raw, str) else raw
                    events.append({
                        "meta": payload.get("meta", {}),
                        "grand_total": inv.get("total_amount", 0)
                    })
            except Exception:
                continue

        # Generate combined ICS
        ics_content = generate_subscription_ics(events)

        # Write to static/calendar.ics
        cal_path = os.path.join(static_dir, "calendar.ics")
        with open(cal_path, "w", encoding="utf-8") as f:
            f.write(ics_content)

    except Exception as e:
        print(f"[ICS] Failed to regenerate static calendar: {e}")
