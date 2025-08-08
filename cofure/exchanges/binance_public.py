from cofure.utils.http import client

BASE = "https://fapi.binance.com"  # Binance Futures (USDT-M)

async def futures_24hr() -> list[dict]:
    """
    Lấy toàn bộ 24h ticker (public). Dùng để:
    - Lọc USDT-M pairs
    - Xếp hạng theo quoteVolume/priceChangePercent
    """
    async with client() as c:
        r = await c.get(f"{BASE}/fapi/v1/ticker/24hr")
        r.raise_for_status()
        data = r.json()
        # loại token đòn bẩy UP/DOWN
        return [
            d for d in data
            if d.get("symbol","").endswith("USDT")
            and "UPUSDT" not in d["symbol"]
            and "DOWNUSDT" not in d["symbol"]
        ]

async def klines(symbol: str, interval: str="15m", limit: int=200):
    """
    OHLCV cho tính tín hiệu (public).
    interval: 1m, 5m, 15m, 1h, 4h, ...
    """
    async with client() as c:
        r = await c.get(
            f"{BASE}/fapi/v1/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit}
        )
        r.raise_for_status()
        return r.json()

async def premium_index(symbols: list[str] | None = None):
    """
    Funding/premium (public). Có thể dùng để làm tín hiệu khẩn.
    """
    async with client() as c:
        r = await c.get(f"{BASE}/fapi/v1/premiumIndex")
        r.raise_for_status()
        items = r.json()
        if symbols:
            sy = set(symbols)
            items = [x for x in items if x.get("symbol") in sy]
        return items
