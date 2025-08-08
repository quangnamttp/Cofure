from datetime import datetime
import pytz
from ..config import TZ_NAME

tz = pytz.timezone(TZ_NAME)

def now_vn():
    return datetime.now(tz)

def fmt(dt=None):
    if dt is None:
        dt = now_vn()
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
