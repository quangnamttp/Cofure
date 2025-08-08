import aiohttp
from datetime import datetime
from typing import List, Dict, Any, Optional
import pytz
import os

# lấy từ ENV (thêm ENV này trên Render nếu có proxy JSON từ ForexFactory)
MACRO_ENDPOINT = os.getenv("MACRO_ENDPOINT", "")
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

IMPORTANT = {"CPI", "Core CPI", "FOMC", "Fed", "Interest Rate", "Unemployment", "Non-Farm", "PPI", "GDP"}

def _to_vn(dt_str: str) -> Optional[datetime]:
    if not dt_str:
        return None
    # chấp nhận chuỗi UTC "YYYY-mm-dd HH:MM" hoặc ISO
    fmts = ["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"]
    for fmt in fmts:
        try:
            dt = datetime.strptime(dt_str, fmt)
            if "Z" in fmt:
                dt = dt.replace(tzinfo=pytz.utc)
            elif dt.tzinfo is None:
                dt = pytz.utc.localize(dt)
            return dt.astimezone(VN_TZ)
        except Exception:
            continue
    return None

def _vi(title: str) -> str:
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
    }
    out = title or ""
    for k, v in rep.items():
        out = out.replace(k, v)
    return out or "Sự kiện vĩ mô"

async def fetch_macro_today() -> List[Dict[str, Any]]:
    """
    Kỳ vọng MACRO_ENDPOINT trả list các object:
    { "id": "...", "time": "YYYY-mm-dd HH:MM" (UTC), "title": "CPI", "impact": "high|medium|low", "forecast": "...", "previous": "..." }
    Không có endpoint → trả []
    """
    if not MACRO_ENDPOINT:
        return []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(MACRO_ENDPOINT, timeout=aiohttp.ClientTimeout(total=12)) as r:
                if r.status != 200:
                    return []
                data = await r.json()
    except Exception:
        return []
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
