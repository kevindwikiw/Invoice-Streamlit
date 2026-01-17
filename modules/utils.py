import io
from typing import Any, List, Dict, Tuple

def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default

def normalize_db_records(raw_data: Any) -> List[Dict[str, Any]]:
    """Normalizes DB output into list[dict]."""
    if raw_data is None:
        return []
    if hasattr(raw_data, "to_dict"):
        try:
            return raw_data.to_dict("records")
        except Exception:
            return []
    if isinstance(raw_data, list):
        return raw_data
    return []

def calculate_totals(items: List[Dict[str, Any]], cashback: float, min_qty: int = 1) -> Tuple[float, float]:
    subtotal = sum(
        safe_float(item.get("Price", 0)) * max(min_qty, safe_int(item.get("Qty", 1), 1))
        for item in items
    )
    grand_total = max(0.0, subtotal - max(0.0, cashback))
    return subtotal, grand_total

def sanitize_text(text: Any) -> str:
    """Tiny HTML escape w/o imports."""
    s = str(text or "")
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;").replace(">", "&gt;")
    s = s.replace('"', "&quot;").replace("'", "&#x27;")
    return s

def desc_to_lines(desc_clean: str) -> List[str]:
    lines: List[str] = []
    for raw in (desc_clean or "").split("\n"):
        s = str(raw).strip()
        if not s:
            continue
        s = s.lstrip("-•·").strip()
        if s:
            lines.append(s)
    return lines

def normalize_desc_text(raw: Any) -> str:
    s = str(raw or "")
    s = s.replace("&lt;", "<").replace("&gt;", ">")
    out = []
    i = 0
    n = len(s)
    while i < n:
        if s[i] == "<" and i + 2 < n and s[i:i+3].lower() == "<br":
            j = i + 3
            while j < n and s[j] != ">":
                j += 1
            if j < n and s[j] == ">":
                out.append("\n")
                i = j + 1
                continue
        out.append(s[i])
        i += 1

    s = "".join(out)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    return s.strip()

def is_valid_email(email: str) -> bool:
    e = (email or "").strip()
    if not e or " " in e or "@" not in e:
        return False
    local, domain = e.rsplit("@", 1)
    if not local or not domain or "." not in domain:
        return False
    if domain.startswith(".") or domain.endswith(".") or ".." in e:
        return False
    return True

import re

def make_safe_filename(inv_no: str, prefix: str = "INV") -> str:
    inv_no = (inv_no or prefix).strip()
    # Replace common separators with underscore
    s = inv_no.replace("/", "_").replace("\\", "_")
    # Remove unsafe filesystem chars, but keep & and spaces
    s = re.sub(r'[<>:"/\\|?*]', '', s)
    return s.strip() or "invoice"

def image_to_base64(uploaded_file) -> str:
    """Converts uploaded file to optimized base64 string (JPEG, resized)."""
    try:
        from PIL import Image
        import base64
        
        image = Image.open(uploaded_file)
        
        # Convert to RGB (in case of PNG with transparency)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
            
        # Resize if huge (max dimension 1024px)
        max_size = 1024
        if max(image.size) > max_size:
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
        # Save to buffer as JPEG
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=85, optimize=True)
        return base64.b64encode(buf.getvalue()).decode()
        
    except Exception as e:
        # Fallback to raw if PIL fails
        try:
             import base64
             return base64.b64encode(uploaded_file.getvalue()).decode()
        except:
             return ""

def rupiah(value: Any) -> str:
    """Formats number as Indonesian Rupiah (e.g. Rp 1.000.000)."""
    val = safe_float(value)
    return f"Rp {val:,.0f}".replace(",", ".")
