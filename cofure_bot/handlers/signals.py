import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from ..signals.engine import generate_batch

# Danh sách coin cần quét
COINS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]

async def send_signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    signals = await generate_batch(COINS, count=5)
    for sig in signals:
        msg = (
            f"📈 {sig['token']} – {sig['side']}\n"
            f"💰 Entry: {sig['entry']}\n"
            f"🎯 TP: {sig['tp']}\n"
            f"🛡️ SL: {sig['sl']}\n"
            f"📊 Độ mạnh: {sig['strength']}%\n"
            f"📌 Lý do: {sig['reason']}\n"
            f"🕒 {sig['time']}"
        )
        await update.message.reply_text(msg)
        await asyncio.sleep(1)  # tránh spam nhanh quá
