import pandas as pd
from cofure.exchanges.binance_public import futures_24hr, klines
from cofure.signals.rules import calc_signal
from cofure.utils.time import fmt_vn
from cofure.utils.format import num

class Signal:
    def __init__(self, symbol, side, type_, order, entry, tp, sl, score, label, reason):
        self.symbol = symbol
        self.side = side
        self.type = type_
        self.order = order
        self.entry = entry
        self.tp = tp
        self.sl = sl
        self.score = score
        self.label = label
        self.reason = reason
        self.vn_time = fmt_vn()

async def generate_signals_max5():
    """
    Lấy top 5 cặp theo volume 24h và tạo tín hiệu cơ bản.
    """
    tickers = await futures_24hr()
    top5 = sorted(tickers, key=lambda x: float(x["quoteVolume"]), reverse=True)[:5]
    signals = []

    for t in top5:
        sym = t["symbol"]
        raw = await klines(sym, "15m", 200)
        df = pd.DataFrame(raw, columns=[
            "time","open","high","low","close","volume","_1","_2","_3","_4","_5","_6"
        ])
        df = df.astype({"open":float,"high":float,"low":float,"close":float,"volume":float})

        siginfo = calc_signal(df)
        if not siginfo["side"]:
            continue

        last_close = df["close"].iloc[-1]
        entry = num(last_close)
        tp = num(last_close * (1.003 if siginfo["side"]=="LONG" else 0.997))
        sl = num(last_close * (0.997 if siginfo["side"]=="LONG" else 1.003))

        s = Signal(
            symbol=sym,
            side=siginfo["side"],
            type_="Scalping",
            order="Market",
            entry=entry,
            tp=tp,
            sl=sl,
            score=siginfo["score"],
            label=siginfo["label"],
            reason=siginfo["reason"]
        )
        signals.append(s)

    return signals
