import aiohttp
import asyncio
from datetime import datetime
import pytz
from ..data.binance_client import quick_signal_metrics

VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

def now_vn_str():
    return datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")

def _decide_side(metrics):
    # Trend + RSI ưu tiên hướng
    if metrics["ema50"] > metrics["ema200"] and metrics["rsi"] >= 45:
        return "LONG"
    if metrics["ema50"] < metrics["ema200"] and metrics["rsi"] <= 55:
        return "SHORT"
    # trung tính → dựa thêm funding
    return "LONG" if metrics["funding"] >= 0 else "SHORT"

def _strength(metrics, side):
    score = 50
    # xu hướng
    if (metrics["ema50"] > metrics["ema200"] and side == "LONG") or (metrics["ema50"] < metrics["ema200"] and side == "SHORT"):
        score += 10
    # volume bùng nổ
    if metrics["vol_ratio"] > 1.2:
        score += min(15, (metrics["vol_ratio"] - 1.2) * 20)
    # RSI cực trị
    if metrics["rsi"] < 35 or metrics["rsi"] > 65:
        score += 10
    # funding lệch
    if abs(metrics["funding"]) > 0.01:
        score += 10
    return max(30, min(95, int(score)))

def _levels(entry, side, pct=0.006):  # ~0.6%
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

    reason = []
    reason.append(f"EMA50 {'>' if m['ema50']>m['ema200'] else '<'} EMA200")
    reason.append(f"RSI {m['rsi']:.1f}")
    reason.append(f"Funding {m['funding']:.4f}")
    reason.append(f"Volume x{m['vol_ratio']:.2f}")

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
    syms = list(symbols)[:]
    # lấy 5 con đầu danh sách (có thể random nếu muốn đa dạng)
    tasks = [generate_signal(s) for s in syms[:count]]
    return await asyncio.gather(*tasks)
