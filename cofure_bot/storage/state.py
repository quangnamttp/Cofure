# cofure_bot/storage/state.py
from datetime import datetime
import pytz
from cofure_bot.config import TZ_NAME

VN_TZ = pytz.timezone(TZ_NAME)

_state = {
    "signals_sent": 0,
    "alerts_sent": 0,
    "last_alert_symbol_at": {},   # {symbol: datetime}
    "last_alert_hour_count": {},  # {"YYYYmmddHH": int}
    "last_sticky_message_id": None,  # int|None (cho private chat)
}

# ===== Counters =====
def bump_signals(n: int = 1):
    _state["signals_sent"] += n

def bump_alerts(n: int = 1):
    _state["alerts_sent"] += n

def snapshot():
    return {
        "signals_sent": _state["signals_sent"],
        "alerts_sent": _state["alerts_sent"],
    }

# ===== Cooldown per symbol =====
def can_alert_symbol(symbol: str, cooldown_minutes: int) -> bool:
    last = _state["last_alert_symbol_at"].get(symbol)
    if not last:
        return True
    now = datetime.now(VN_TZ)
    return (now - last).total_seconds() >= cooldown_minutes * 60

def mark_alert_symbol(symbol: str):
    _state["last_alert_symbol_at"][symbol] = datetime.now(VN_TZ)

# ===== Hourly cap =====
def _hour_key() -> str:
    return datetime.now(VN_TZ).strftime("%Y%m%d%H")

def can_alert_this_hour(max_per_hour: int) -> bool:
    key = _hour_key()
    return _state["last_alert_hour_count"].get(key, 0) < max_per_hour

def bump_alert_hour():
    key = _hour_key()
    _state["last_alert_hour_count"][key] = _state["last_alert_hour_count"].get(key, 0) + 1

# ===== Sticky message (private chat) =====
def get_sticky_message_id():
    return _state["last_sticky_message_id"]

def set_sticky_message_id(mid: int):
    _state["last_sticky_message_id"] = mid
