from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot
from cofure.config import get_settings
from cofure.utils.time import fmt_vn
from cofure.exchanges.binance_public import futures_24hr
from cofure.signals.engine import generate_signals_max5
from cofure.macro.source import load_today_items

async def job_morning(bot: Bot):
    s = get_settings()
    tickers = await futures_24hr()
    top = sorted(
        [t for t in tickers if t.get("symbol","").endswith("USDT")],
        key=lambda x: float(x.get("priceChangePercent", 0)), reverse=True
    )[:5]
    movers = "\n".join([f"• {t['symbol']}: {float(t['priceChangePercent']):+.2f}%" for t in top])
    msg = (
        f"☀️ Chào buổi sáng nhé bạn  |  usd = vnd\n"
        f"— Top tăng 24h —\n{movers}\n\n"
        f"Xu hướng: BTC ... | ETH ...\n"
        f"Funding: BTC ... | ETH ...\n"
        f"({fmt_vn()})"
    )
    await bot.send_message(chat_id=s.telegram_chat_id, text=msg)

async def job_macro(bot: Bot):
    s = get_settings()
    items = await load_today_items()
    if not items:
        await bot.send_message(s.telegram_chat_id, "📅 Hôm nay không có tin vĩ mô quan trọng.\nChúc bạn một ngày trade thật thành công nha!")
        return
    lines = ["📅 Lịch vĩ mô hôm nay:"]
    for it in items:
        lines.append(f"• {it.time} — {it.event} — Ảnh hưởng: {it.impact}")
    lines.append("Gợi ý: Tin mạnh → đứng ngoài 5–15’ sau khi ra tin.")
    await bot.send_message(s.telegram_chat_id, "\n".join(lines))

async def job_signals(bot: Bot):
    s = get_settings()
    sigs = await generate_signals_max5()
    for sig in sigs:
        text = (
            f"📈 {sig.symbol} — {'🟩 LONG' if sig.side=='LONG' else '🟥 SHORT'}\n\n"
            f"{'🟢' if sig.type=='Scalping' else '🔵'} Loại lệnh: {sig.type}\n"
            f"🔹 Kiểu vào lệnh: {sig.order}\n"
            f"💰 Entry: {sig.entry}\n"
            f"🎯 TP: {sig.tp}\n"
            f"🛡️ SL: {sig.sl}\n"
            f"📊 Độ mạnh: {sig.score}% ({sig.label})\n"
            f"📌 Lý do: {sig.reason}\n"
            f"🕒 Thời gian: {sig.vn_time}"
        )
        await bot.send_message(s.telegram_chat_id, text)

async def job_summary(bot: Bot):
    s = get_settings()
    await bot.send_message(s.telegram_chat_id, f"🌙 Tổng kết hôm nay ({fmt_vn()}):\nHiệu suất: cập nhật sau…\nCảm ơn bạn đã đồng hành cùng Cofure. Ngủ ngon nha! 😴")

def schedule_all(app):
    s = get_settings()
    bot = app.bot
    sch = AsyncIOScheduler(timezone=s.tz)

    # 06:00
    sch.add_job(job_morning, CronTrigger(hour=6, minute=0), kwargs={"bot": bot})
    # 07:00
    sch.add_job(job_macro, CronTrigger(hour=7, minute=0), kwargs={"bot": bot})
    # 06:00–22:00 mỗi 30'
    sch.add_job(job_signals, CronTrigger(hour="6-21", minute="0,30"), kwargs={"bot": bot})
    # 22:00
    sch.add_job(job_summary, CronTrigger(hour=22, minute=0), kwargs={"bot": bot})

    sch.start()
