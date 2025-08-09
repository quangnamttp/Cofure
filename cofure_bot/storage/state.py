# cofure_bot/storage/state.py

from datetime import datetime, timedelta
import pytz
from cofure_bot.config import TZ_NAME

VN_TZ = pytz.timezone(TZ_NAME)

_state = {
    "signals_sent": 0,
    "alerts_sent": 0,
    "last_alert_symbol_at": {},   # {symbol: datetime}
    "last_sticky_message_id": None,  # int | None
    "last_alert_hour_count": {},  # {"YYYYmmddHH": int}
}

def bump_signals(n=1):
    _state["signals_sent"] += n

def bump_alerts(n=1):
    _state["alerts_sent"] += n

def snapshot():
    return {
        "signals_sent": _state["signals_sent"],
        "alerts_sent": _state["alerts_sent"],
    }

# === Urgent helpers ===
def can_alert_symbol(symbol: str, cooldown_minutes: int) -> bool:
    t = _state["last_alert_symbol_at"].get(symbol)
    if not t:
        return True
    now = datetime.now(VN_TZ)
    return (now - t).total_seconds() >= cooldown_minutes * 60

def mark_alert_symbol(symbol: str):
    _state["last_alert_symbol_at"][symbol] = datetime.now(VN_TZ)

def can_alert_this_hour(max_per_hour: int) -> bool:
    now = datetime.now(VN_TZ)
    key = now.strftime("%Y%m%d%H")
    count = _state["last_alert_hour_count"].get(key, 0)
    return count < max_per_hour

def bump_alert_hour():
    now = datetime.now(VN_TZ)
    key = now.strftime("%Y%m%d%H")
    _state["last_alert_hour_count"][key] = _state["last_alert_hour_count"].get(key, 0) + 1

def get_sticky_message_id():
    return _state["last_sticky_message_id"]

def set_sticky_message_id(mid: int):
    _state["last_sticky_message_id"] = mid
