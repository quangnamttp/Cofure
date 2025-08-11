import aiohttp
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import pytz

VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

FF_THISWEEK = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# Từ khóa sự kiện quan trọng tác động mạnh tới crypto (IN HOA để so khớp)
CRYPTO_KEYS = {
    "CPI", "CORE CPI",
    "PCE", "CORE PCE",
    "FOMC", "FED",
    "INTEREST RATE", "RATE DECISION", "PRESS CONFERENCE",
    "SPEECH", "SPEAKS",               # ⬅️ thêm phát biểu
    "UNEMPLOYMENT", "UNEMPLOYMENT RATE",
    "NON-FARM", "NFP",
    "PPI", "GDP", "RETAIL SALES",
    "ISM", "PMI"
}

IMPACT_MAP = {1: "Low", 2: "Medium", 3: "High", 4: "Holiday"}

# Mức tối thiểu để giữ sự kiện: 3=High, 2=Medium
IMPACT_MIN_LEVEL = 2  # ⬅️ cho phép Medium trở lên (điều chỉnh 3 nếu muốn chỉ High)

def _impact_level(label: str) -> int:
    l = (label or "").lower()
    if l.startswith("high"): return 3
    if l.startswith("medium"): return 2
    if l.startswith("low"): return 1
    if l.startswith("holiday"): return 4
    # fallback: cố map theo chuỗi số
    try:
        return int(label)
    except Exception:
        return 0

def _parse_dt_any(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        ts = float(v)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
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
    if raw is None:
        return ""
    if isinstance(raw, (int, float)):
        return IMPACT_MAP.get(int(raw), str(raw))
    if isinstance(raw, str):
        return raw.capitalize()
    if isinstance(raw, dict):
        return raw.get("label") or IMPACT_MAP.get(raw.get("value"), "")
    return str(raw)

def _clean_field(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    if s.upper() in {"NA", "N/A", "-"}:
        return ""
    return s

def _vi(title: str) -> str:
    rep = {
        "Core CPI": "CPI lõi",
        "CPI": "Chỉ số giá tiêu dùng (CPI)",
        "Core PCE": "PCE lõi",
        "PCE": "Chi tiêu tiêu dùng cá nhân (PCE)",
        "Interest Rate": "Quyết định lãi suất",
        "Rate Decision": "Quyết định lãi suất",
        "Press Conference": "Họp báo",
        "Speech": "Bài phát biểu",
        "Speaks": "Phát biểu",
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
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FF_THISWEEK, timeout=aiohttp.ClientTimeout(total=12)) as r:
                if r.status != 200:
                    return []
                return await r.json()
    except Exception:
        return []

def _pick_actual(e: Dict[str, Any]) -> str:
    cands = ["actual", "value", "result", "release"]
    for k in cands:
        v = e.get(k)
        if isinstance(v, dict):
            vv = v.get("value") or v.get("text")
            if vv:
                return _clean_field(vv)
        if v not in (None, ""):
            return _clean_field(v)
    return ""

def _filter_events_crypto_high(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for e in raw or []:
        title = str(e.get("title") or e.get("event") or "")
        if not title:
            continue

        dt_utc = (
            _parse_dt_any(e.get("timestamp")) or
            _parse_dt_any(e.get("dateTime")) or
            _parse_dt_any(e.get("date")) or
            _parse_dt_any(e.get("updated"))
        )
        if not dt_utc:
            continue
        t_vn = _to_vn(dt_utc)

        impact = _norm_impact(e.get("impact"))
        if _impact_level(impact) < IMPACT_MIN_LEVEL:
            continue

        title_up = title.upper()
        if not any(k in title_up for k in CRYPTO_KEYS):
            continue

        forecast = _clean_field(e.get("forecast") or e.get("consensus") or e.get("expected"))
        previous = _clean_field(e.get("previous") or e.get("prior"))
        actual   = _pick_actual(e)

        out.append({
            "id": str(e.get("id") or f"{title}-{int(t_vn.timestamp())}"),
            "time_vn": t_vn,
            "title_en": title,
            "title_vi": _vi(title),
            "impact": impact,
            "forecast": forecast,
            "previous": previous,
            "actual": actual,
        })
    out.sort(key=lambda x: x["time_vn"])
    return out

# ====== PUBLIC ======
async def fetch_macro_for_date(target_date_vn) -> List[Dict[str, Any]]:
    raw = await _fetch_ff_week()
    if not raw:
        return []
    events = _filter_events_crypto_high(raw)
    return [e for e in events if e["time_vn"].date() == target_date_vn]

async def fetch_macro_today() -> List[Dict[str, Any]]:
    today = datetime.now(VN_TZ).date()
    return await fetch_macro_for_date(today)

async def fetch_macro_tomorrow() -> List[Dict[str, Any]]:
    tomorrow = (datetime.now(VN_TZ) + timedelta(days=1)).date()
    return await fetch_macro_for_date(tomorrow)

async def fetch_macro_week() -> List[Dict[str, Any]]:
    raw = await _fetch_ff_week()
    if not raw:
        return []
    events = _filter_events_crypto_high(raw)
    now = datetime.now(VN_TZ)
    monday = (now - timedelta(days=now.weekday())).date()
    sunday = monday + timedelta(days=6)
    return [e for e in events if monday <= e["time_vn"].date() <= sunday]
