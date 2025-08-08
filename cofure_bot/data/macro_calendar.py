import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pytz
import os

# Lấy endpoint JSON của lịch vĩ mô từ ENV (có thể để trống)
MACRO_ENDPOINT = os.getenv("MACRO_ENDPOINT", "")
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

# Từ khóa/sự kiện quan trọng để lọc
IMPORTANT = {
    "CPI", "Core CPI", "FOMC", "Fed", "Interest Rate",
    "Unemployment", "Non-Farm", "PPI", "GDP", "Retail Sales", "PMI"
}

def _to_vn(dt_str: str) -> Optional[datetime]:
    """Parse chuỗi thời gian (UTC) và trả datetime theo giờ VN."""
    if not dt_str:
        return None
    fmts = ["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"]
    for fmt in fmts:
        try:
            dt = datetime.strptime(dt_str, fmt)
            if "Z" in fmt or dt.tzinfo is None:
                dt = pytz.utc.localize(dt)
            return dt.astimezone(VN_TZ)
        except Exception:
            continue
    return None

def _vi(title: str) -> str:
    """Dịch tiêu đề sự kiện sang TV thân thiện."""
    rep = {
        "Core CPI": "CPI lõi",
        "CPI": "Chỉ số giá tiêu dùng (CPI)",
        "Interest Rate": "Quyết định lãi suất",
        "Unemployment": "Tỷ lệ thất nghiệp",
        "Non-Farm": "Bảng lương phi nông nghiệp (NFP)",
        "Retail Sales": "Doanh số bán lẻ",
        "GDP": "Tổng sản phẩm quốc nội (GDP)",
        "PPI": "Chỉ số giá sản xuất (PPI)",
        "FOMC": "FOMC",
        "PMI": "PMI",
    }
    out = title or ""
    for k, v in rep.items():
        out = out.replace(k, v)
    return out or "Sự kiện vĩ mô"

async def _fetch_raw() -> List[Dict[str, Any]]:
    """Gọi endpoint JSON (nếu có). Không có → [] để bot vẫn chạy."""
    if not MACRO_ENDPOINT:
        return []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(MACRO_ENDPOINT, timeout=aiohttp.ClientTimeout(total=12)) as r:
                if r.status != 200:
                    return []
                return await r.json()
    except Exception:
        return []

def _filter_events(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Chuẩn hóa + lọc theo IMPORTANT/impact cao, sort theo thời gian VN."""
    out: List[Dict[str, Any]] = []
    for e in data or []:
        t = _to_vn(str(e.get("time", "")))
        if not t:
            continue
        title = str(e.get("title", ""))
        impact = (e.get("impact") or "").lower()
        if any(k in title for k in IMPORTANT) or impact in {"high", "very high"}:
            out.append({
                "id": e.get("id") or f"{title}-{int(t.timestamp())}",
                "time_vn": t,
                "title_vi": _vi(title),
                "impact": impact.capitalize() if impact else "",
                "forecast": e.get("forecast") or "",
                "previous": e.get("previous") or "",
            })
    out.sort(key=lambda x: x["time_vn"])
    return out

# ====== HÀM PUBLIC CHO BOT ======
async def fetch_macro_for_date(target_date_vn) -> List[Dict[str, Any]]:
    """Sự kiện quan trọng của 1 ngày (giờ VN)."""
    raw = await _fetch_raw()
    if not raw:
        return []
    events = _filter_events(raw)
    return [e for e in events if e["time_vn"].date() == target_date_vn]

async def fetch_macro_today() -> List[Dict[str, Any]]:
    """Sự kiện quan trọng của HÔM NAY (giờ VN)."""
    today = datetime.now(VN_TZ).date()
    return await fetch_macro_for_date(today)

async def fetch_macro_week() -> List[Dict[str, Any]]:
    """Sự kiện quan trọng của tuần hiện tại (Thứ 2→CN, giờ VN)."""
    raw = await _fetch_raw()
    if not raw:
        return []
    events = _filter_events(raw)
    now = datetime.now(VN_TZ)
    monday = (now - timedelta(days=now.weekday())).date()
    sunday = monday + timedelta(days=6)
    return [e for e in events if monday <= e["time_vn"].date() <= sunday]
