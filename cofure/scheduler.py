import asyncio
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

# Scheduler toàn cục (gắn timezone VN)
_SCHED: AsyncIOScheduler | None = None

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
    """07:00 — gửi lịch vĩ mô (chỉ tin High) theo giờ VN."""
    s = get_settings()
    items = await load_today_items()
    if not items:
        await bot.send_message(
            s.telegram_chat_id,
            "📅 Hôm nay không có tin vĩ mô quan trọng.\nChúc bạn một ngày trade thật thành công nha!"
        )
        return
    lines = [f"📅 Hôm nay {now_vn().strftime('%A, %d/%m/%Y')} (chỉ tin High)"]
    for it in items:
        lines.append(f"• {it.time} — {it.event} — Ảnh hưởng: High")
    lines.append("Gợi ý: Tin mạnh → đứng ngoài 5–15’ sau khi ra tin.")
    await bot.send_message(s.telegram_chat_id, "\n".join(lines))

async def _schedule_macro_alerts(bot: Bot):
    """06:55 — đọc lịch hôm nay và tạo job: pre-alert (T-5’), on-release (T), follow-up (T+10’)."""
    global _SCHED
    s = get_settings()
    sch = _SCHED
    if sch is None:
        return
    items = await load_today_items()
    now = now_vn()

    for it in items:
        # parse HH:MM VN
        try:
            h, m = map(int, it.time.split(":"))
        except Exception:
            continue

        event_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if event_time <= now:
            continue  # bỏ sự kiện đã qua

        # T-5'
        pre_t = event_time - timedelta(minutes=5)
        if pre_t > now:
            sch.add_job(
                lambda ev=it: asyncio.create_task(bot.send_message(s.telegram_chat_id, build_prealert(ev))),
                trigger=DateTrigger(run_date=pre_t)
            )
        # T
        sch.add_job(
            lambda ev=it: asyncio.create_task(bot.send_message(s.telegram_chat_id, build_onrelease(ev))),
            trigger=DateTrigger(run_date=event_time)
        )
        # T+10'
        fol_t = event_time + timedelta(minutes=10)
        sch.add_job(
            lambda ev=it: asyncio.create_task(bot.send_message(s.telegram_chat_id, build_followup(ev))),
            trigger=DateTrigger(run_date=fol_t)
        )

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
    await bot.send_message(
        s.telegram_chat_id,
        f"🌙 Tổng kết hôm nay ({fmt_vn()}):\nHiệu suất: cập nhật sau…\nCảm ơn bạn đã đồng hành cùng Cofure. Ngủ ngon nha! 😴"
    )

def schedule_all(app):
    """Đăng ký toàn bộ lịch chạy định kỳ."""
    global _SCHED
    s = get_settings()
    bot = app.bot
    sch = AsyncIOScheduler(timezone=s.tz)

    # 06:55 — đọc lịch hôm nay và lên job cảnh báo theo từng sự kiện High
    sch.add_job(lambda: asyncio.create_task(_schedule_macro_alerts(bot)), CronTrigger(hour=6, minute=55))
    # 07:00 — gửi lịch vĩ mô của ngày
    sch.add_job(job_macro, CronTrigger(hour=7, minute=0), kwargs={"bot": bot})
    # 06:00 — chào buổi sáng
    sch.add_job(job_morning, CronTrigger(hour=6, minute=0), kwargs={"bot": bot})
    # 06:00–22:00 — mỗi 30'
    sch.add_job(job_signals, CronTrigger(hour="6-21", minute="0,30"), kwargs={"bot": bot})
    # 22:00 — tổng kết
    sch.add_job(job_summary, CronTrigger(hour=22, minute=0), kwargs={"bot": bot})

    sch.start()
    _SCHED = sch
