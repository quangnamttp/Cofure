import aiohttp
from telegram import Update
from telegram.ext import ContextTypes
import pytz
from datetime import datetime, timedelta

from cofure_bot.config import TELEGRAM_ALLOWED_USER_ID, TZ_NAME
from cofure_bot.data.macro_calendar import fetch_macro_for_date
from cofure_bot.data.binance_client import active_symbols, quick_signal_metrics
from cofure_bot.signals.engine import generate_batch
from cofure_bot.scheduler.jobs import (
    _fmt_signal, MIN_QUOTE_VOL, MAX_CANDIDATES,
    ALERT_FUNDING, ALERT_VOLRATIO,
    job_morning, job_macro
)

VN_TZ = pytz.timezone(TZ_NAME)

def _authorized(update: Update) -> bool:
    u = update.effective_user
    return bool(u and u.id == TELEGRAM_ALLOWED_USER_ID)

# ===== Helpers: format lịch vĩ mô =====
def _fmt_events_header(day: datetime) -> str:
    dow = day.isoweekday()  # 1..7
    return f"📅 Thứ {dow}, ngày {day.strftime('%d/%m/%Y')}"

def _fmt_events(day: datetime, events: list) -> str:
    if not events:
        return _fmt_events_header(day) + "\n\nHôm nay/Ngày này không có tin tức vĩ mô quan trọng.\nChúc bạn một ngày trade thật thành công nha!"
    now = datetime.now(VN_TZ)
    lines = [_fmt_events_header(day), "", "🧭 Lịch tin vĩ mô quan trọng:"]
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
    return "\n".join(lines)

# ===== Commands trong menu =====
async def lich_hom_nay_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update): return
    day = datetime.now(VN_TZ)
    events = await fetch_macro_for_date(day.date())
    await update.message.reply_text(_fmt_events(day, events))

async def lich_ngay_mai_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update): return
    day = datetime.now(VN_TZ) + timedelta(days=1)
    events = await fetch_macro_for_date(day.date())
    await update.message.reply_text(_fmt_events(day, events))

async def lich_ca_tuan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update): return
    today = datetime.now(VN_TZ)
    monday = today - timedelta(days=today.weekday())  # Thứ 2 tuần hiện tại
    texts = []
    for i in range(7):
        d = monday + timedelta(days=i)
        ev = await fetch_macro_for_date(d.date())
        texts.append(_fmt_events(d, ev))
    # Ngăn tin quá dài: gửi theo từng ngày, hoặc gộp nhẹ
    chunk = "\n\n" + ("—" * 8) + "\n\n"
    joined = chunk.join(texts)
    # Telegram giới hạn 4096 ký tự mỗi tin -> chia nhỏ nếu cần
    while joined:
        part = joined[:3500]
        cut = part.rfind("\n")
        if cut == -1: cut = len(part)
        await update.message.reply_text(part[:cut])
        joined = joined[cut:].lstrip("\n")

async def test_full_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Chạy ngay: chào sáng → lịch vĩ mô → 5 tín hiệu (riêng lẻ) → tối đa 2 cảnh báo khẩn → mô phỏng tổng kết.
    Không phụ thuộc khung giờ.
    """
    if not _authorized(update): return
    await update.message.reply_text("🚀 Bắt đầu test FULL: chào sáng → lịch vĩ mô → 5 tín hiệu → cảnh báo khẩn → tổng kết.")

    # 1) Chào buổi sáng + top gainers (tận dụng job sẵn)
    try:
        await job_morning(context)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi phần chào sáng: {e}")

    # 2) Lịch vĩ mô hôm nay (tận dụng job sẵn)
    try:
        await job_macro(context)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi phần lịch vĩ mô: {e}")

    # 3) 5 tín hiệu RIÊNG LẺ — bỏ qua khung giờ
    try:
        async with aiohttp.ClientSession() as session:
            syms = await active_symbols(session, min_quote_volume=MIN_QUOTE_VOL)
        if not syms:
            syms = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"]
        sigs = await generate_batch(syms[:MAX_CANDIDATES], count=5)
        for i, s in enumerate(sigs):
            s["signal_type"] = "Scalping" if i < 3 else "Swing"
            s["order_type"] = "Market"
            await update.message.reply_text(_fmt_signal(s))
    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi phần tín hiệu: {e}")

    # 4) Cảnh báo khẩn — quét nhanh, tối đa 2 cảnh báo
    try:
        sent = 0
        async with aiohttp.ClientSession() as session:
            syms = await active_symbols(session, min_quote_volume=MIN_QUOTE_VOL)
            for sym in syms[:MAX_CANDIDATES]:
                m = await quick_signal_metrics(session, sym, interval="5m")
                if abs(m["funding"]) >= ALERT_FUNDING or m["vol_ratio"] >= ALERT_VOLRATIO:
                    arrow = "▲" if m["vol_ratio"] >= ALERT_VOLRATIO else ""
                    side_hint = "Long nghiêng" if m["funding"] > 0 else ("Short nghiêng" if m["funding"] < 0 else "Trung tính")
                    text = (f"⏰ Cảnh báo khẩn — {sym}\n"
                            f"• Funding: {m['funding']:.4f} ({side_hint})\n"
                            f"• Volume 5m: x{m['vol_ratio']:.2f} {arrow}\n"
                            f"• Gợi ý: cân nhắc {'MUA' if m['funding']>0 else 'BÁN' if m['funding']<0 else 'quan sát'} nếu ổn định thêm.")
                    await update.message.reply_text(text)
                    sent += 1
                    if sent >= 2:
                        break
    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi phần cảnh báo khẩn: {e}")

    # 5) Mô phỏng tổng kết
    try:
        await update.message.reply_text(
            "🌒 Tổng kết phiên (mô phỏng)\n"
            "• Tín hiệu đã gửi: ~5 (trong test)\n"
            "• Cảnh báo khẩn: ~0–2 (trong test)\n"
            "• Dự báo tối: Giữ kỷ luật, giảm đòn bẩy khi biến động mạnh.\n\n"
            "🌙 Cảm ơn bạn đã đồng hành cùng Cofure hôm nay. 😴 Ngủ ngon nha!"
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi phần tổng kết: {e}")
