from dataclasses import dataclass
from typing import List
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from cofure.utils.http import client

@dataclass
class MacroItem:
    time: str   # HH:MM (giờ VN)
    event: str
    impact: str # High
    note: str | None = None

FF_URL = "https://www.forexfactory.com/calendar?day=today"

def to_vn_time(hhmm: str) -> str:
    """Chuyển từ HH:MM GMT -> Asia/Ho_Chi_Minh (+7)."""
    try:
        h, m = hhmm.strip().split(":")
        dt_gmt = datetime.now(timezone.utc).replace(hour=int(h), minute=int(m), second=0, microsecond=0)
        dt_vn = dt_gmt + timedelta(hours=7)
        return dt_vn.strftime("%H:%M")
    except Exception:
        return hhmm

def _clean_text(x: str) -> str:
    return " ".join((x or "").split())

async def load_today_items() -> List[MacroItem]:
    """Lấy lịch hôm nay từ ForexFactory, CHỈ lọc High."""
    try:
        async with client() as c:
            r = await c.get(FF_URL)
            r.raise_for_status()
            html = r.text

        soup = BeautifulSoup(html, "html.parser")
        items: List[MacroItem] = []

        for row in soup.select("tr.calendar__row"):
            time_el = row.select_one(".calendar__time")
            ev_el = row.select_one(".calendar__event-title, .calendar__event")
            imp_el = row.select_one(".calendar__impact, .impact")
            if not (time_el and ev_el and imp_el):
                continue

            raw_time = _clean_text(time_el.get_text())
            raw_event = _clean_text(ev_el.get_text())
            raw_imp = _clean_text(imp_el.get_text()) or _clean_text(imp_el.get("title") or "")

            # Chỉ giữ High
            if "High" not in raw_imp:
                continue

            if raw_time and raw_time != "--":
                hhmm_vn = to_vn_time(raw_time)
            else:
                continue

            items.append(MacroItem(time=hhmm_vn, event=raw_event, impact="High"))

        def _to_minutes(t: str) -> int:
            try:
                h, m = map(int, t.split(":"))
                return h * 60 + m
            except Exception:
                return 9999

        items.sort(key=lambda x: _to_minutes(x.time))
        return items
    except Exception:
        return []
