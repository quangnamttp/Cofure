import aiohttp
import datetime as dt
from datetime import datetime
from telegram.ext import Application, ContextTypes, JobQueue
import pytz
from ..config import TELEGRAM_ALLOWED_USER_ID, TZ_NAME
from ..signals.engine import generate_batch
from ..data.binance_client import active_symbols, top_gainers, quick_signal_metrics
from ..data.macro_calendar import fetch_macro_today
from ..storage.state import bump_signals, bump_alerts, snapshot

VN_TZ = pytz.timezone(TZ_NAME)

# Ngưỡng & cấu hình
MIN_QUOTE_VOL = 5_000_000.0   # lọc cặp volume >= 5 triệu USDT/24h
MAX_CANDIDATES = 60           # giới hạn số symbol đem đi tính
ALERT_MAX_PER_RUN = 3         # tối đa 3 cảnh báo mỗi lần quét
ALERT_FUNDING = 0.02          # |funding| >= 2%o
ALERT_VOLRATIO = 1.8          # bùng nổ volume >= x1.8 so với MA20
WORK_START = 6
WORK_END = 22

def _in_work_hours() -> bool:
    now = datetime.now(VN_TZ)
    return WORK_START <= now.hour < WORK_END

def _fmt_signal(sig: dict) -> str:
    # nhãn sức mạnh
    label = "Mạnh" if sig["strength"] >= 70 else ("Tiêu chuẩn" if sig["strength"] >= 50 else "Tham khảo")
    side_square = "🟩" if sig["side"] == "LONG" else "🟥"
    return (
        f"📈 {sig['token']} — {side_square} {sig['side']}\n\n"
        f"🟢 Loại lệnh: {sig.get('signal_type','Scalping')}\n"
        f"🔹 Kiểu vào lệnh: {sig.get('order_type','Market')}\n"
        f"💰 Entry: {sig['entry']}\n"
        f"🎯 TP: {sig['tp']}\n"
        f"🛡️ SL: {sig['sl']}\n"
        f"📊 Độ mạnh: {sig['strength']}% ({label})\n"
        f"📌 Lý do: RSI={sig['rsi']}, EMA9={sig['ema9']}, EMA21={sig['ema21']}\n"
        f"🕒 Thời gian: {sig['time']}"
    )

# === 06:00 — Chào buổi sáng + top gainers ===
async def job_morning(context: ContextTypes.DEFAULT_TYPE):
    async with aiohttp.ClientSession() as session:
        gainers = await top_gainers(session, 5)
    lines = ["Chào buổi sáng nhé Cofure ☀️  (USD≈VND - tham chiếu)", "", "🔥 5 đồng tăng trưởng nổi bật (24h):"]
    for g in gainers:
        sym = g.get("symbol")
        chg = float(g.get("priceChangePercent", 0) or 0)
        vol = float(g.get("quoteVolume", 0) or 0)
        lines.append(f"• <b>{sym}</b> ▲ {chg:.2f}% | Volume: {vol:,.0f} USDT")
    lines.append("")
    lines.append("📊 Funding, volume, xu hướng sẽ có trong tín hiệu định kỳ suốt ngày.")
    await context.bot.send_message(chat_id=TELEGRAM_ALLOWED_USER_ID, text="\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)

# === 07:00 — Lịch vĩ mô hôm nay ===
async def job_macro(context: ContextTypes.DEFAULT_TYPE):
    events = await fetch_macro_today()
    now = datetime.now(VN_TZ)
    header = f"📅 Hôm nay là Thứ {now.isoweekday()}, ngày {now.strftime('%d/%m/%Y')}"
    if not events:
        await context.bot.send_message(chat_id=TELEGRAM_ALLOWED_USER_ID, text=header + "\n\nHôm nay không có tin tức vĩ mô quan trọng.\nChúc bạn một ngày trade thật thành công nha!")
        return
    lines = [header, "", "🧭 Lịch tin vĩ mô quan trọng:"]
    for e in events:
        tstr = e["time_vn"].strftime("%H:%M")
        extra = []
        if e.get("forecast"): extra.append(f"Dự báo {e['forecast']}")
        if e.get("previous"): extra.append(f"Trước {e['previous']}")
        extra_str = (" — " + ", ".join(extra)) if extra else ""
        # đếm ngược
        left = e["time_vn"] - now
        if left.total_seconds() > 0:
            h = int(left.total_seconds() // 3600)
            m = int((left.total_seconds() % 3600)//60)
            countdown = f" — ⏳ còn {h} giờ {m} phút" if h else f" — ⏳ còn {m} phút"
        else:
            countdown = ""
        lines.append(f"• {tstr} — {e['title_vi']} — Ảnh hưởng: {e['impact']}{extra_str}{countdown}")
    lines.append("\n💡 Gợi ý: Đứng ngoài 5–10’ quanh giờ ra tin; quan sát funding/volume.")
    await context.bot.send_message(chat_id=TELEGRAM_ALLOWED_USER_ID, text="\n".join(lines))

# === 06:00→22:00 — Mỗi 30' gửi 5 tín hiệu RIÊNG LẺ ===
async def job_halfhour_signals(context: ContextTypes.DEFAULT_TYPE):
    if not _in_work_hours():
        return
    async with aiohttp.ClientSession() as session:
        syms = await active_symbols(session, min_quote_volume=MIN_QUOTE_VOL)
    if not syms:
        syms = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"]
    candidates = syms[:MAX_CANDIDATES]
    signals = await generate_batch(candidates, count=5)
    # 3 Scalping + 2 Swing
    for i, s in enumerate(signals):
        s["signal_type"] = "Scalping" if i < 3 else "Swing"
        s["order_type"] = "Market"
        await context.bot.send_message(chat_id=TELEGRAM_ALLOWED_USER_ID, text=_fmt_signal(s))
        bump_signals(1)

# === 06:00→22:00 — Mỗi 5' cảnh báo khẩn khi funding/volume bất thường ===
async def job_urgent_alerts(context: ContextTypes.DEFAULT_TYPE):
    if not _in_work_hours():
        return
    alerts = 0
    async with aiohttp.ClientSession() as session:
        syms = await active_symbols(session, min_quote_volume=MIN_QUOTE_VOL)
        for sym in syms[:MAX_CANDIDATES]:
            try:
                m = await quick_signal_metrics(session, sym, interval="5m")
                if abs(m["funding"]) >= ALERT_FUNDING or m["vol_ratio"] >= ALERT_VOLRATIO:
                    arrow = "▲" if m["vol_ratio"] >= ALERT_VOLRATIO else ""
                    side_hint = "Long nghiêng" if m["funding"] > 0 else ("Short nghiêng" if m["funding"] < 0 else "Trung tính")
                    text = (f"⏰ Cảnh báo khẩn — {sym}\n"
                            f"• Funding: {m['funding']:.4f} ({side_hint})\n"
                            f"• Volume 5m: x{m['vol_ratio']:.2f} {arrow}\n"
                            f"• Gợi ý: cân nhắc {'MUA' if m['funding']>0 else 'BÁN' if m['funding']<0 else 'quan sát'} nếu ổn định thêm.")
                    await context.bot.send_message(chat_id=TELEGRAM_ALLOWED_USER_ID, text=text)
                    bump_alerts(1)
                    alerts += 1
                    if alerts >= ALERT_MAX_PER_RUN:
                        break
            except Exception:
                continue

# === 22:00 — Tổng kết phiên ===
async def job_night_summary(context: ContextTypes.DEFAULT_TYPE):
    snap = snapshot()
    text = (
        "🌒 Tổng kết phiên\n"
        f"• Tín hiệu đã gửi: {snap['signals_sent']}\n"
        f"• Cảnh báo khẩn: {snap['alerts_sent']}\n"
        "• Dự báo tối: Giữ kỷ luật, giảm đòn bẩy khi biến động mạnh.\n\n"
        "🌙 Cảm ơn bạn đã đồng hành cùng Cofure hôm nay. 😴 Ngủ ngon nha!"
    )
    await context.bot.send_message(chat_id=TELEGRAM_ALLOWED_USER_ID, text=text)

def setup_jobs(app: Application):
    # Đảm bảo JobQueue tồn tại trong chế độ webhook
    jq = app.job_queue
    if jq is None:
        jq = JobQueue()
        jq.set_application(app)
        jq.start()
        app.job_queue = jq

    # Lịch cố định theo giờ VN
    jq.run_daily(job_morning,       time=dt.time(hour=6,  minute=0, tzinfo=VN_TZ), name="morning_0600")
    jq.run_daily(job_macro,         time=dt.time(hour=7,  minute=0, tzinfo=VN_TZ), name="macro_0700")
    jq.run_repeating(job_halfhour_signals, interval=1800, first=5,  name="signals_30m")   # mỗi 30'
    jq.run_repeating(job_urgent_alerts,    interval=300,  first=15, name="alerts_5m")     # mỗi 5'
    jq.run_daily(job_night_summary, time=dt.time(hour=22, minute=0, tzinfo=VN_TZ), name="summary_2200")
