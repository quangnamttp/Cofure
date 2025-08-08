import aiohttp
import asyncio
from datetime import datetime
import pytz
from ..data.binance_client import quick_signal_metrics

VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

def now_vn_str():
    return datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")

def _decide_side(m):
    if m["ema50"] > m["ema200"] and m["rsi"] >= 45:
        return "LONG"
    if m["ema50"] < m["ema200"] and m["rsi"] <= 55:
        return "SHORT"
    return "LONG" if m["funding"] >= 0 else "SHORT"

def _strength(m, side):
    score = 50
    if (m["ema50"] > m["ema200"] and side == "LONG") or (m["ema50"] < m["ema200"] and side == "SHORT"):
        score += 10
    if m["vol_ratio"] > 1.2:
        score += min(15, (m["vol_ratio"] - 1.2) * 20)
    if m["rsi"] < 35 or m["rsi"] > 65:
        score += 10
    if abs(m["funding"]) > 0.01:
        score += 10
    return max(30, min(95, int(score)))

def _levels(entry, side, pct=0.006):
    if side == "LONG":
        tp = entry * (1 + pct * 1.5)
        sl = entry * (1 - pct)
    else:
        tp = entry * (1 - pct * 1.5)
        sl = entry * (1 + pct)
    return round(tp, 6), round(sl, 6)

async def generate_signal(symbol: str) -> dict:
    async with aiohttp.ClientSession() as session:
        m = await quick_signal_metrics(session, symbol, interval="5m")
    side = _decide_side(m)
    entry = float(m["last"])
    tp, sl = _levels(entry, side)
    strength = _strength(m, side)
    reason = [
        f"EMA50 {'>' if m['ema50']>m['ema200'] else '<'} EMA200",
        f"RSI {m['rsi']:.1f}",
        f"Funding {m['funding']:.4f}",
        f"Volume x{m['vol_ratio']:.2f}",
    ]
    return {
        "token": symbol,
        "side": side,
        "entry": round(entry, 6),
        "tp": tp,
        "sl": sl,
        "strength": strength,
        "reason": ", ".join(reason),
        "time": now_vn_str(),
    }

async def generate_batch(symbols: list, count: int = 5):
    tasks = [generate_signal(s) for s in symbols[:count]]
    return await asyncio.gather(*tasks)
