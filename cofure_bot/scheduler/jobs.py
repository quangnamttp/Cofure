import asyncio
from telegram.ext import Application, ContextTypes
from datetime import datetime
import pytz
from ..config import TELEGRAM_ALLOWED_USER_ID, TZ_NAME
from ..signals.engine import generate_batch

VN_TZ = pytz.timezone(TZ_NAME)

COINS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
         "DOGEUSDT","ADAUSDT","AVAXUSDT","LINKUSDT","TONUSDT"]

def _in_work_hours() -> bool:
    now = datetime.now(VN_TZ)
    return 6 <= now.hour < 22

def _fmt(sig: dict) -> str:
    return (
        f"📈 {sig['token']} – {sig['side']}\n"
        f"💰 Entry: {sig['entry']}\n"
        f"🎯 TP: {sig['tp']}\n"
        f"🛡️ SL: {sig['sl']}\n"
        f"📊 Độ mạnh: {sig['strength']}%\n"
        f"📌 Lý do: {sig['reason']}\n"
        f"🕒 {sig['time']}"
    )

async def job_halfhour_signals(context: ContextTypes.DEFAULT_TYPE):
    if not _in_work_hours():
        return
    signals = await generate_batch(COINS, count=5)
    # Gửi gộp một tin cho gọn (5 lệnh, ngăn cách dòng trống)
    text = "\n\n".join(_fmt(s) for s in signals)
    await context.bot.send_message(
        chat_id=TELEGRAM_ALLOWED_USER_ID,
        text=text
    )

def setup_jobs(app: Application):
    # Lặp mỗi 30 phút. Bắt đầu ngay khi service chạy, job tự kiểm tra khung giờ VN.
    app.job_queue.run_repeating(job_halfhour_signals, interval=1800, first=5, name="signals_30m")
