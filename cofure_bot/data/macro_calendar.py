# cofure_bot/data/macro_calendar.py

import aiohttp
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import pytz

VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

# JSON feed chính thức của ForexFactory cho tuần hiện tại
FF_THISWEEK = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# Từ khóa sự kiện quan trọng tác động mạnh tới crypto (so khớp chữ IN HOA)
CRYPTO_KEYS = {
    "CPI", "CORE CPI",
    "PCE", "CORE PCE",
    "FOMC", "FED",
    "INTEREST RATE", "RATE DECISION", "PRESS CONFERENCE",
    "UNEMPLOYMENT", "UNEMPLOYMENT RATE",
    "NON-FARM", "NFP",
    "PPI", "GDP", "RETAIL SALES",
    "ISM", "PMI"
}

IMPACT_MAP = {1: "Low", 2: "Medium", 3: "High", 4: "Holiday"}

def _parse_dt_any(v: Any) -> Optional[datetime]:
    """
    Cố gắng parse mọi kiểu thời gian FF trả:
    - 'timestamp' (s hoặc ms)
    - ISO8601 string ('2025-08-08T12:30:00Z' / '...+00:00')
    - 'date' + 'time' (ít gặp)
    """
    if v is None:
        return None
    # số: timestamp (s hoặc ms)
    if isinstance(v, (int, float)):
        ts = float(v)
        if ts > 1e12:  # ms
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    # chuỗi ISO
    if isinstance(v, str):
        s = v.strip()
        if s.endswith("Z"):
            s = s.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
    return None

def _to_vn(dt_utc: datetime) -> datetime:
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(VN_TZ)

def _norm_impact(raw: Any) -> str:
    """FF có thể trả impact dưới dạng số, chuỗi, hoặc object."""
    if raw is None:
        return ""
    if isinstance(raw, (int, float)):
        return IMPACT_MAP.get(int(raw), str(raw))
    if isinstance(raw, str):
        return raw.capitalize()
    if isinstance(raw, dict):
        # một số feed có { "impact": { "value": 3, "label": "High" } }
        return raw.get("label") or IMPACT_MAP.get(raw.get("value"), "")
    return str(raw)

def _vi(title: str) -> str:
    rep = {
        "Core CPI": "CPI lõi",
        "CPI": "Chỉ số giá tiêu dùng (CPI)",
        "Core PCE": "PCE lõi",
        "PCE": "Chi tiêu tiêu dùng cá nhân (PCE)",
        "Interest Rate": "Quyết định lãi suất",
        "Rate Decision": "Quyết định lãi suất",
        "Press Conference": "Họp báo",
        "Unemployment Rate": "Tỷ lệ thất nghiệp",
        "Unemployment": "Tỷ lệ thất nghiệp",
        "Non-Farm": "Bảng lương phi nông nghiệp (NFP)",
        "NFP": "Bảng lương phi nông nghiệp (NFP)",
        "Retail Sales": "Doanh số bán lẻ",
        "GDP": "Tổng sản phẩm quốc nội (GDP)",
        "PPI": "Chỉ số giá sản xuất (PPI)",
        "FOMC": "FOMC",
        "PMI": "PMI",
        "ISM": "Chỉ số ISM",
        "Fed": "Fed",
    }
    out = title or ""
    for k, v in rep.items():
        out = out.replace(k, v)
    return out or "Sự kiện vĩ mô"

async def _fetch_ff_week() -> List[Dict[str, Any]]:
    """Tải lịch tuần hiện tại trực tiếp từ ForexFactory."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FF_THISWEEK, timeout=aiohttp.ClientTimeout(total=12)) as r:
                if r.status != 200:
                    return []
                return await r.json()
    except Exception:
        return []

def _filter_events_crypto_high(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Giữ sự kiện:
      - Thuộc nhóm từ khóa CRYPTO_KEYS (bắt buộc)
      - Impact cao: High / Very High (bắt buộc)
    Chuẩn hóa field và quy đổi giờ VN.
    """
    out: List[Dict[str, Any]] = []
    for e in raw or []:
        title = str(e.get("title") or e.get("event") or "")
        if not title:
            continue

        # thời gian
        dt_utc = (
            _parse_dt_any(e.get("timestamp")) or
            _parse_dt_any(e.get("dateTime")) or
            _parse_dt_any(e.get("date")) or
            _parse_dt_any(e.get("updated"))
        )
        if not dt_utc:
            continue
        t_vn = _to_vn(dt_utc)

        # impact
        impact = _norm_impact(e.get("impact"))
        impact_ok = impact.lower() in {"high", "very high"}

        # từ khóa
        title_up = title.upper()
        key_ok = any(k in title_up for k in CRYPTO_KEYS)

        if not (key_ok and impact_ok):
            continue

        out.append({
            "id": str(e.get("id") or f"{title}-{int(t_vn.timestamp())}"),
            "time_vn": t_vn,
            "title_vi": _vi(title),
            "impact": impact,
            "forecast": str(e.get("forecast") or e.get("consensus") or ""),
            "previous": str(e.get("previous") or ""),
        })
    out.sort(key=lambda x: x["time_vn"])
    return out

# ====== HÀM PUBLIC CHO BOT ======
async def fetch_macro_for_date(target_date_vn) -> List[Dict[str, Any]]:
    """Sự kiện crypto-impact-cao của 1 ngày (giờ VN) – dữ liệu thật từ ForexFactory."""
    raw = await _fetch_ff_week()
    if not raw:
        return []
    events = _filter_events_crypto_high(raw)
    return [e for e in events if e["time_vn"].date() == target_date_vn]

async def fetch_macro_today() -> List[Dict[str, Any]]:
    today = datetime.now(VN_TZ).date()
    return await fetch_macro_for_date(today)

async def fetch_macro_week() -> List[Dict[str, Any]]:
    raw = await _fetch_ff_week()
    if not raw:
        return []
    events = _filter_events_crypto_high(raw)
    now = datetime.now(VN_TZ)
    monday = (now - timedelta(days=now.weekday())).date()
    sunday = monday + timedelta(days=6)
    return [e for e in events if monday <= e["time_vn"].date() <= sunday]
