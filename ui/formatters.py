# ui/formatters.py

def rupiah(val) -> str:
    try:
        n = int(float(val))
        return f"Rp {n:,}".replace(",", ".")
    except Exception:
        return "Rp 0"
