def pct(x: float) -> str:
    try:
        return f"{x:+.2f}%"
    except Exception:
        return str(x)

def num(x: float) -> str:
    try:
        if abs(x) >= 1000:
            # 1,234 -> "1.234" cho dễ đọc VN
            return f"{x:,.0f}".replace(",", ".")
        return f"{x:.4f}".rstrip('0').rstrip('.')
    except Exception:
        return str(x)
