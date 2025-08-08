import aiohttp
from telegram.ext import Application, ContextTypes, JobQueue  # <-- thêm JobQueue
from datetime import datetime
import pytz
from ..config import TELEGRAM_ALLOWED_USER_ID, TZ_NAME
from ..signals.engine import generate_batch
from ..data.binance_client import active_symbols

VN_TZ = pytz.timezone(TZ_NAME)

MIN_QUOTE_VOL = 5_000_000.0   # lọc cặp có volume >= 5 triệu USDT/24h
MAX_CANDIDATES = 60           # tối đa số symbol đem đi tính để tiết kiệm API

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
    # lấy tất cả cặp futures USDT có volume ổn định
    async with aiohttp.ClientSession() as session:
        syms = await active_symbols(session, min_quote_volume=MIN_QUOTE_VOL)
    if not syms:
        syms = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"]  # fallback

    candidates = syms[:MAX_CANDIDATES]
    signals = await generate_batch(candidates, count=5)

    text = "\n\n".join(_fmt(s) for s in signals)
    await context.bot.send_message(chat_id=TELEGRAM_ALLOWED_USER_ID, text=text)

def setup_jobs(app: Application):
    # Đảm bảo JobQueue tồn tại trong chế độ webhook
    jq = app.job_queue
    if jq is None:
        jq = JobQueue()
        jq.set_application(app)
        jq.start()
        app.job_queue = jq

    # chạy mỗi 30 phút; job tự check khung giờ VN
    jq.run_repeating(job_halfhour_signals, interval=1800, first=5, name="signals_30m")
