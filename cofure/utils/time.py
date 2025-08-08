from datetime import datetime
import zoneinfo
from cofure.config import get_settings

def now_vn():
    tz = zoneinfo.ZoneInfo(get_settings().tz)
    return datetime.now(tz)

def fmt_vn(dt: datetime | None = None) -> str:
    dt = dt or now_vn()
    return dt.strftime("%H:%M %d/%m/%Y")
