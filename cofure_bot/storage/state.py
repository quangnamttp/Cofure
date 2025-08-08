from datetime import datetime
import pytz

VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

STATE = {
    "date": datetime.now(VN_TZ).strftime("%Y-%m-%d"),
    "signals_sent": 0,
    "alerts_sent": 0,
}

def _ensure_today():
    today = datetime.now(VN_TZ).strftime("%Y-%m-%d")
    if STATE["date"] != today:
        STATE["date"] = today
        STATE["signals_sent"] = 0
        STATE["alerts_sent"] = 0

def bump_signals(n=1):
    _ensure_today()
    STATE["signals_sent"] += n

def bump_alerts(n=1):
    _ensure_today()
    STATE["alerts_sent"] += n

def snapshot():
    _ensure_today()
    return dict(STATE)
