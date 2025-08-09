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
    # Lạm phát & tiêu dùng
    "CPI", "CORE CPI", "CPI Y/Y", "CPI M/M",
    "PCE", "CORE PCE", "PCE Y/Y", "PCE M/M",
    "PPI", "CORE PPI", "PPI Y/Y", "PPI M/M",
    # Việc làm
    "UNEMPLOYMENT", "UNEMPLOYMENT RATE", "JOBLESS", "NON-FARM", "NFP", "PAYROLLS",
    # Lãi suất & họp báo
    "INTEREST RATE", "RATE DECISION", "RATE STATEMENT", "PRESS CONFERENCE",
    "FOMC", "FED", "DOT PLOT",
    # Tăng trưởng & hoạt động
    "GDP", "RETAIL SALES", "ISM", "PMI"
}

IMPACT_MAP = {1: "Low", 2: "Medium", 3: "High", 4: "Holiday"}

def _parse_dt_any(v: Any) -> Optional[datetime]:
    """
    Parse các kiểu thời gian mà FF có thể trả:
    - timestamp (s hoặc ms)
    - ISO8601 (2025-08-08T12:30:00Z / ...+00:00)
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        ts = float(v)
        if ts > 1e12:  # ms
            ts = ts / 1000.0
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
    """
    FF có thể trả impact dưới dạng số, chuỗi hoặc object.
    Trả về label chuẩn hóa: Low / Medium / High / Holiday / Very High (nếu có).
    """
    if raw is None:
        return ""
    if isinstance(raw, (int, float)):
        return IMPACT_MAP.get(int(raw), str(raw))
    if isinstance(raw, str):
        lab = raw.strip().title()
        # Nhiều feed dùng 'High' / 'Medium' / 'Low' — hoặc 'High Impact Expected'
        if "High" in lab and "Very" in lab:
            return "Very High"
        if "High" in lab and "Very" not in lab:
            return "High"
        if "Medium" in lab:
            return "Medium"
        if "Low" in lab:
            return "Low"
        if "Holiday" in lab:
            return "Holiday"
        return lab
    if isinstance(raw, dict):
        lab = raw.get("label") or IMPACT_MAP.get(raw.get("value"), "")
        return _norm_impact(lab)
    return str(raw)

def _vi(title: str) -> str:
    rep = {
        "Core CPI": "CPI lõi",
        "CPI": "Chỉ số giá tiêu dùng (CPI)",
        "Core PCE": "PCE lõi",
        "PCE": "Chi tiêu tiêu dùng cá nhân (PCE)",
        "Core PPI": "PPI lõi",
        "PPI": "Chỉ số giá sản xuất (PPI)",
        "Interest Rate": "Quyết định lãi suất",
        "Rate Decision": "Quyết định lãi suất",
        "Rate Statement": "Tuyên bố lãi suất",
        "Press Conference": "Họp báo",
        "Unemployment Rate": "Tỷ lệ thất nghiệp",
        "Unemployment": "Thất nghiệp",
        "Jobless": "Thất nghiệp",
        "Non-Farm": "Bảng lương phi nông nghiệp (NFP)",
        "NFP": "Bảng lương phi nông nghiệp (NFP)",
        "Retail Sales": "Doanh số bán lẻ",
        "GDP": "Tổng sản phẩm quốc nội (GDP)",
        "FOMC": "FOMC",
        "PMI": "PMI",
        "ISM": "Chỉ số ISM",
        "Fed": "Fed",
        "Dot Plot": "Biểu đồ điểm (Dot Plot)",
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
    Chuẩn hoá field, quy đổi giờ VN, và giữ thêm 'title' gốc + 'actual' + 'country'.
    """
    out: List[Dict[str, Any]] = []
    for e in raw or []:
        title = str(e.get("title") or e.get("event") or "")
        if not title:
            continue

        # thời gian
        dt_utc = (
            _parse_dt_any(e.get("timestamp"))
            or _parse_dt_any(e.get("dateTime"))
            or _parse_dt_any(e.get("date"))
            or _parse_dt_any(e.get("updated"))
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
            "title": title,                  # EN gốc (phục vụ phân tích)
            "title_vi": _vi(title),          # bản Việt để hiển thị
            "impact": impact,
            "forecast": str(e.get("forecast") or e.get("consensus") or ""),
            "previous": str(e.get("previous") or ""),
            "actual": str(e.get("actual") or ""),        # <-- BỔ SUNG: để post-analysis
            "country": str(e.get("country") or ""),      # tuỳ lúc có/không
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
