import asyncio
import logging
from datetime import timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from telegram import Bot

from cofure.config import get_settings
from cofure.utils.time import now_vn, fmt_vn
from cofure.exchanges.binance_public import futures_24hr
from cofure.signals.engine import generate_signals_max5
from cofure.macro.source import load_today_items
from cofure.macro.advisor import build_prealert, build_onrelease, build_followup

log = logging.getLogger("cofure.scheduler")

_SCHED: AsyncIOScheduler | None = None

async def job_morning(bot: Bot):
    log.info("[06:00] Running morning job…")
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
    log.info("[06:00] Morning message sent")

async def job_macro(bot: Bot):
    log.info("[07:00] Running macro calendar job…")
    s = get_settings()
    items = await load_today_items()
    if not items:
        await bot.send_message(
            s.telegram_chat_id,
            "📅 Hôm nay không có tin vĩ mô quan trọng.\nChúc bạn một ngày trade thật thành công nha!"
        )
        log.info("[07:00] No macro news today")
        return
    lines = [f"📅 Hôm nay {now_vn().strftime('%A, %d/%m/%Y')} (chỉ tin High)"]
    for it in items:
        lines.append(f"• {it.time} — {it.event} — Ảnh hưởng: High")
    lines.append("Gợi ý: Tin mạnh → đứng ngoài 5–15’ sau khi ra tin.")
    await bot.send_message(s.telegram_chat_id, "\n".join(lines))
    log.info(f"[07:00] Macro calendar sent with {len(items)} events")

async def _schedule_macro_alerts(bot: Bot):
    log.info("[06:55] Scheduling macro alerts for today…")
    global _SCHED
    s = get_settings()
    sch = _SCHED
    if sch is None:
        log.warning("Scheduler not initialized")
        return
    items = await load_today_items()
    now = now_vn()

    for it in items:
        try:
            h, m = map(int, it.time.split(":"))
        except Exception:
            continue

        event_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if event_time <= now:
            continue

        pre_t = event_time - timedelta(minutes=5)
        if pre_t > now:
            sch.add_job(
                lambda ev=it: asyncio.create_task(bot.send_message(s.telegram_chat_id, build_prealert(ev))),
                trigger=DateTrigger(run_date=pre_t)
            )
            log.info(f"[06:55] Scheduled pre-alert for {it.event} at {pre_t.strftime('%H:%M')}")

        sch.add_job(
            lambda ev=it: asyncio.create_task(bot.send_message(s.telegram_chat_id, build_onrelease(ev))),
            trigger=DateTrigger(run_date=event_time)
        )
        log.info(f"[06:55] Scheduled on-release for {it.event} at {event_time.strftime('%H:%M')}")

        fol_t = event_time + timedelta(minutes=10)
        sch.add_job(
            lambda ev=it: asyncio.create_task(bot.send_message(s.telegram_chat_id, build_followup(ev))),
            trigger=DateTrigger(run_date=fol_t)
        )
        log.info(f"[06:55] Scheduled follow-up for {it.event} at {fol_t.strftime('%H:%M')}")

async def job_signals(bot: Bot):
    log.info("[Signal] Generating trading signals…")
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
    log.info(f"[Signal] Sent {len(sigs)} signals")

async def job_summary(bot: Bot):
    log.info("[22:00] Sending daily summary…")
    s = get_settings()
    await bot.send_message(
        s.telegram_chat_id,
        f"🌙 Tổng kết hôm nay ({fmt_vn()}):\nHiệu suất: cập nhật sau…\nCảm ơn bạn đã đồng hành cùng Cofure. Ngủ ngon nha! 😴"
    )
    log.info("[22:00] Summary sent")

def schedule_all(app):
    global _SCHED
    s = get_settings()
    bot = app.bot
    sch = AsyncIOScheduler(timezone=s.tz)

    sch.add_job(lambda: asyncio.create_task(_schedule_macro_alerts(bot)), CronTrigger(hour=6, minute=55))
    sch.add_job(job_macro, CronTrigger(hour=7, minute=0), kwargs={"bot": bot})
    sch.add_job(job_morning, CronTrigger(hour=6, minute=0), kwargs={"bot": bot})
    sch.add_job(job_signals, CronTrigger(hour="6-21", minute="0,30"), kwargs={"bot": bot})
    sch.add_job(job_summary, CronTrigger(hour=22, minute=0), kwargs={"bot": bot})

    sch.start()
    _SCHED = sch
    log.info("Scheduler started")
