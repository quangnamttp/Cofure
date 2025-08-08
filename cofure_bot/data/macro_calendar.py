import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pytz
import os

MACRO_ENDPOINT = os.getenv("MACRO_ENDPOINT", "")
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

IMPORTANT = {
    "CPI", "Core CPI", "FOMC", "Fed", "Interest Rate",
    "Unemployment", "Non-Farm", "PPI", "GDP", "Retail Sales", "PMI"
}

def _to_vn(dt_str: str) -> Optional[datetime]:
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

def _vn_to_utc_str(dt_vn: datetime) -> str:
    return dt_vn.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")

def _mock_raw_week() -> List[Dict[str, Any]]:
    now = datetime.now(VN_TZ)
    monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    wed_cpi   = (monday + timedelta(days=2)).replace(hour=19, minute=30)
    thu_fomc  = (monday + timedelta(days=3)).replace(hour=1,  minute=0)
    fri_nfp   = (monday + timedelta(days=4)).replace(hour=19, minute=30)
    return [
        {"id": "cpi-us", "time": _vn_to_utc_str(wed_cpi), "title": "US CPI", "impact": "high"},
        {"id": "fomc",   "time": _vn_to_utc_str(thu_fomc), "title": "FOMC Interest Rate", "impact": "high"},
        {"id": "nfp-us", "time": _vn_to_utc_str(fri_nfp), "title": "US Non-Farm Payrolls", "impact": "high"},
    ]

async def _fetch_raw() -> List[Dict[str, Any]]:
    # Không có endpoint -> luôn trả mock để test được
    if not MACRO_ENDPOINT:
        return _mock_raw_week()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(MACRO_ENDPOINT, timeout=aiohttp.ClientTimeout(total=12)) as r:
                if r.status != 200:
                    return _mock_raw_week()  # fallback
                data = await r.json()
                # Nếu endpoint trả rỗng -> cũng fallback để bạn luôn có dữ liệu test
                return data if data else _mock_raw_week()
    except Exception:
        return _mock_raw_week()

def _filter_events(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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

async def fetch_macro_for_date(target_date_vn) -> List[Dict[str, Any]]:
    raw = await _fetch_raw()
    events = _filter_events(raw)
    day = [e for e in events if e["time_vn"].date() == target_date_vn]
    # 🔁 Nếu ngày đó vẫn rỗng -> tạo mock ngay trong ngày đó (đảm bảo luôn có dữ liệu để bạn test)
    if not day:
        mock_time = datetime.combine(target_date_vn, datetime.min.time()).replace(tzinfo=VN_TZ).replace(hour=19, minute=30)
        day = [{
            "id": f"mock-{target_date_vn.isoformat()}",
            "time_vn": mock_time,
            "title_vi": "CPI (mock)",
            "impact": "High",
            "forecast": "",
            "previous": "",
        }]
    return day

async def fetch_macro_today() -> List[Dict[str, Any]]:
    today = datetime.now(VN_TZ).date()
    return await fetch_macro_for_date(today)

async def fetch_macro_week() -> List[Dict[str, Any]]:
    raw = await _fetch_raw()
    events = _filter_events(raw)
    now = datetime.now(VN_TZ)
    monday = (now - timedelta(days=now.weekday())).date()
    sunday = monday + timedelta(days=6)
    week = [e for e in events if monday <= e["time_vn"].date() <= sunday]
    if not week:  # nếu cũng rỗng -> trả mock tuần
        return _filter_events(_mock_raw_week())
    return week
