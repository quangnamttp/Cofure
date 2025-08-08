import pandas as pd
import ta

def calc_signal(df: pd.DataFrame) -> dict:
    """
    Nhận DataFrame OHLCV → trả về tín hiệu
    df: cột [open, high, low, close, volume]
    """
    close = df["close"]
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
    ema_fast = ta.trend.EMAIndicator(close, window=9).ema_indicator().iloc[-1]
    ema_slow = ta.trend.EMAIndicator(close, window=21).ema_indicator().iloc[-1]

    side = None
    score = 50  # mặc định

    if ema_fast > ema_slow and rsi > 55:
        side = "LONG"
        score += 20
        if rsi > 65:
            score += 10
    elif ema_fast < ema_slow and rsi < 45:
        side = "SHORT"
        score += 20
        if rsi < 35:
            score += 10

    label = "Mạnh" if score >= 70 else "Tiêu chuẩn" if score >= 50 else "Tham khảo"

    return {
        "side": side,
        "score": score,
        "label": label,
        "reason": f"RSI={rsi:.1f}, EMA9={ema_fast:.3f}, EMA21={ema_slow:.3f}"
    }
