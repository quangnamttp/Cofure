import aiohttp
from typing import List, Dict, Any
from ..utils.net import with_retry

BINANCE_FAPI = "https://fapi.binance.com"
HEADERS = {"Accept": "application/json"}

@with_retry(max_attempts=3, base_delay=0.8)
async def _get_json(session: aiohttp.ClientSession, url: str, params: dict = None):
    async with session.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=aiohttp.ClientTimeout(total=15)
    ) as r:
        r.raise_for_status()
        return await r.json()

async def fetch_24h_tickers(session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """
    Trả về toàn bộ 24h tickers của Futures.
    Lọc lấy các symbol kết thúc bằng 'USDT' (perpetual USDT pairs).
    """
    url = f"{BINANCE_FAPI}/fapi/v1/ticker/24hr"
    data = await _get_json(session, url)
    return [d for d in data if isinstance(d, dict) and d.get("symbol", "").endswith("USDT")]

async def top_gainers(session: aiohttp.ClientSession, n: int = 5) -> List[Dict[str, Any]]:
    t = await fetch_24h_tickers(session)
    t = sorted(t, key=lambda x: float(x.get("priceChangePercent", 0) or 0), reverse=True)
    return t[:n]

async def funding_rate_latest(session: aiohttp.ClientSession, symbol: str) -> float:
    url = f"{BINANCE_FAPI}/fapi/v1/fundingRate"
    data = await _get_json(session, url, params={"symbol": symbol, "limit": 1})
    try:
        return float(data[0]["fundingRate"]) if data else 0.0
    except Exception:
        return 0.0

async def klines(session: aiohttp.ClientSession, symbol: str, interval: str = "5m", limit: int = 200):
    url = f"{BINANCE_FAPI}/fapi/v1/klines"
    return await _get_json(session, url, params={"symbol": symbol, "interval": interval, "limit": limit})

# === Chỉ báo cơ bản ===
def rsi(series, period: int = 14) -> float:
    if len(series) <= period:
        return 50.0
    gains, losses = [], []
    for i in range(1, period + 1):
        delta = series[-i] - series[-i - 1]
        (gains if delta >= 0 else losses).append(abs(delta))
    avg_gain = sum(gains) / len(gains) if gains else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 1e-9
    rs = (avg_gain / avg_loss) if avg_loss else 0
    return 100 - (100 / (1 + rs))

def ema(series, period: int):
    if len(series) < period:
        return series[-1]
    k = 2 / (period + 1)
    e = series[-period]
    for p in series[-period + 1:]:
        e = p * k + e * (1 - k)
    return e

async def quick_signal_metrics(session: aiohttp.ClientSession, symbol: str, interval: str = "5m"):
    ks = await klines(session, symbol, interval=interval, limit=200)
    closes = [float(k[4]) for k in ks]
    vol = [float(k[5]) for k in ks]
    last = closes[-1]
    rsi_val = rsi(closes, 14)
    ema50 = ema(closes, 50)
    ema200 = ema(closes, 200 if len(closes) >= 200 else max(10, len(closes) - 1))
    trend = 1 if ema50 > ema200 else -1
    vol_ratio = (vol[-1] / (sum(vol[-20:]) / 20.0)) if len(vol) >= 20 else 1.0
    fund = await funding_rate_latest(session, symbol)
    return {
        "last": last,
        "rsi": rsi_val,
        "ema50": ema50,
        "ema200": ema200,
        "trend": trend,
        "vol_ratio": vol_ratio,
        "funding": fund,
    }

# --- NEW: danh sách symbol có volume ổn định ---
async def active_symbols(session: aiohttp.ClientSession, min_quote_volume: float = 5_000_000.0) -> List[str]:
    """
    Lấy danh sách toàn bộ Futures USDT có quoteVolume >= ngưỡng (mặc định 5 triệu USDT/24h).
    Trả về danh sách symbol, ví dụ ["BTCUSDT", "ETHUSDT", ...]
    """
    tickers = await fetch_24h_tickers(session)
    syms: List[str] = []
    for t in tickers:
        try:
            qv = float(t.get("quoteVolume", 0) or 0)
            if qv >= min_quote_volume:
                syms.append(t["symbol"])
        except Exception:
            continue
    syms.sort()
    return syms
