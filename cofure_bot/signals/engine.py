import aiohttp
import random
from datetime import datetime
from ..data.binance_client import quick_signal_metrics
import pytz

VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

def now_vn():
    return datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%Y")

async def generate_signal(symbol: str) -> dict:
    async with aiohttp.ClientSession() as session:
        metrics = await quick_signal_metrics(session, symbol)

    # Xác định side
    if metrics["trend"] == 1 and metrics["rsi"] > 55:
        side = "LONG"
    elif metrics["trend"] == -1 and metrics["rsi"] < 45:
        side = "SHORT"
    else:
        side = random.choice(["LONG", "SHORT"])

    entry = metrics["last"]
    if side == "LONG":
        tp = entry * (1 + 0.005)   # +0.5%
        sl = entry * (1 - 0.003)   # -0.3%
    else:
        tp = entry * (1 - 0.005)
        sl = entry * (1 + 0.003)

    # Strength
    strength = 50
    if metrics["vol_ratio"] > 1.5:
        strength += 15
    if (side == "LONG" and metrics["funding"] > 0) or (side == "SHORT" and metrics["funding"] < 0):
        strength += 10
    strength = min(strength, 90)

    reason_parts = []
    if metrics["trend"] == 1:
        reason_parts.append("EMA50 > EMA200")
    else:
        reason_parts.append("EMA50 < EMA200")
    reason_parts.append(f"RSI={metrics['rsi']:.1f}")
    reason_parts.append(f"Funding={metrics['funding']:.4f}")
    reason_parts.append(f"VolRatio={metrics['vol_ratio']:.2f}")

    return {
        "token": symbol,
        "side": side,
        "entry": round(entry, 4),
        "tp": round(tp, 4),
        "sl": round(sl, 4),
        "strength": strength,
        "reason": ", ".join(reason_parts),
        "time": now_vn()
    }

async def generate_batch(symbols: list, count: int = 5):
    random.shuffle(symbols)
    tasks = [generate_signal(s) for s in symbols[:count]]
    return await asyncio.gather(*tasks)
