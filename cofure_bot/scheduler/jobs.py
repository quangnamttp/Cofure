# cofure_bot/scheduler/jobs.py

import aiohttp
import datetime as dt
from datetime import datetime
from telegram.ext import Application, ContextTypes, JobQueue
import pytz

from cofure_bot.config import TELEGRAM_ALLOWED_USER_ID, TZ_NAME
from cofure_bot.signals.engine import generate_batch, generate_signal
from cofure_bot.data.binance_client import active_symbols, top_gainers, quick_signal_metrics
from cofure_bot.data.macro_calendar import fetch_macro_today
from cofure_bot.storage.state import (
    bump_signals, bump_alerts, snapshot,
    can_alert_symbol, mark_alert_symbol,
    can_alert_this_hour, bump_alert_hour,
    get_sticky_message_id, set_sticky_message_id,
)

VN_TZ = pytz.timezone(TZ_NAME)

# ========= NGƯỠNG & CẤU HÌNH =========
MIN_QUOTE_VOL   = 5_000_000.0   # lọc cặp volume >= 5 triệu USDT/24h
MAX_CANDIDATES  = 60            # giới hạn số symbol đem đi tính

# Tín hiệu định kỳ
WORK_START      = 6
WORK_END        = 22

# Cảnh báo khẩn - NGƯỠNG CƠ BẢN (lọc sơ bộ)
ALERT_FUNDING   = 0.02          # |funding| >= 2‰
ALERT_VOLRATIO  = 1.8           # bùng nổ volume >= x1.8 so với MA20

# Cảnh báo khẩn - CHỌN LỌC & TẦN SUẤT
ALERT_COOLDOWN_MIN   = 180      # 3 tiếng/coin
ALERT_TOPK           = 2        # lấy tối đa 2 symbol/lượt
ALERT_MAX_PER_RUN    = 3        # chốt an toàn mỗi lượt quét
ALERT_SCORE_MIN      = 3.0      # ngưỡng điểm tổng hợp tối thiểu
ALERT_PER_HOUR_MAX   = 3        # mỗi giờ tối đa 3 tin khẩn
PIN_URGENT           = True     # cố gắng pin nếu có quyền

# Bỏ cooldown nếu cực mạnh:
ALERT_STRONG_VOLRATIO = 3.0     # vol_ratio >= 3.0
ALERT_SCORE_STRONG    = 6.0     # score >= 6.0

# Ngưỡng để gắn ⭐ cho lệnh định kỳ (gần mức khẩn)
STAR_SCORE_THRESHOLD  = 5.0

# ========= TIỆN ÍCH =========
def _in_work_hours() -> bool:
    now = datetime.now(VN_TZ)
    return WORK_START <= now.hour < WORK_END

def _day_name_vi(d: datetime) -> str:
    return {
        1: "Thứ 2",
        2: "Thứ 3",
        3: "Thứ 4",
        4: "Thứ 5",
        5: "Thứ 6",
        6: "Thứ 7",
        7: "Chủ nhật",
    }[d.isoweekday()]

def _fmt_signal(sig: dict) -> str:
    label = "Mạnh" if sig["strength"] >= 70 else ("Tiêu chuẩn" if sig["strength"] >= 50 else "Tham khảo")
    side_square = "🟩" if sig["side"] == "LONG" else "🟥"

    reasons = []
    if "funding" in sig and sig["funding"] is not None:
        reasons.append(f"Funding={sig['funding']:.4f}")
    if "vol_ratio" in sig and sig["vol_ratio"] is not None:
        reasons.append(f"Vol5m=x{sig['vol_ratio']:.2f}")
    if sig.get("rsi") is not None:
        reasons.append(f"RSI={sig['rsi']}")
    if sig.get("ema9") is not None:
        reasons.append(f"EMA9={sig['ema9']}")
    if sig.get("ema21") is not None:
        reasons.append(f"EMA21={sig['ema21']}")
    reason_str = ", ".join(reasons)

    return (
        f"📈 {sig['token']} — {side_square} {sig['side']}\n\n"
        f"🟢 Loại lệnh: {sig.get('signal_type','Scalping')}\n"
        f"🔹 Kiểu vào lệnh: {sig.get('order_type','Market')}\n"
        f"💰 Entry: {sig['entry']}\n"
        f"🎯 TP: {sig['tp']}\n"
        f"🛡️ SL: {sig['sl']}\n"
        f"📊 Độ mạnh: {sig['strength']}% ({label})\n"
        f"📌 Lý do: {reason_str}\n"
        f"🕒 Thời gian: {sig['time']}"
    )

# ========= 06:00 — Chào buổi sáng (USD/VND + top gainers) =========
async def job_morning(context: ContextTypes.DEFAULT_TYPE):
    # Tỷ giá USD/VND (2 nguồn fallback)
    usd_vnd = None
    try:
        async with aiohttp.ClientSession() as s:
            try:
                async with s.get(
                    "https://api.exchangerate.host/latest",
                    params={"base": "USD", "symbols": "VND"},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        usd_vnd = float(data.get("rates", {}).get("VND") or 0) or None
            except Exception:
                pass
            if not usd_vnd:
                async with s.get("https://open.er-api.com/v6/latest/USD",
                                 timeout=aiohttp.ClientTimeout(total=10)) as r2:
                    if r2.status == 200:
                        data2 = await r2.json()
                        usd_vnd = float(data2.get("rates", {}).get("VND") or 0) or None
    except Exception:
        usd_vnd = None

    async with aiohttp.ClientSession() as session:
        gainers = await top_gainers(session, 5)

    if usd_vnd:
        lines = [f"Chào buổi sáng nhé Cofure ☀️  (1 USD ≈ {usd_vnd:,.0f} VND)", ""]
    else:
        lines = ["Chào buổi sáng nhé Cofure ☀️  (USD≈VND - tham chiếu)", ""]
    lines.append("🔥 5 đồng tăng trưởng nổi bật (24h):")
    for g in gainers:
        sym = g.get("symbol")
        chg = float(g.get("priceChangePercent", 0) or 0)
        vol = float(g.get("quoteVolume", 0) or 0)
        lines.append(f"• <b>{sym}</b> ▲ {chg:.2f}% | Volume: {vol:,.0f} USDT")
    lines.append("")
    lines.append("📊 Funding, volume, xu hướng sẽ có trong tín hiệu định kỳ suốt ngày.")

    await context.bot.send_message(
        chat_id=TELEGRAM_ALLOWED_USER_ID,
        text="\n".join(lines),
        parse_mode="HTML",
        disable_web_page_preview=True
    )

# ========= 07:00 — Lịch vĩ mô hôm nay =========
async def job_macro(context: ContextTypes.DEFAULT_TYPE):
    events = await fetch_macro_today()
    now = datetime.now(VN_TZ)
    header = f"📅 {_day_name_vi(now)}, ngày {now.strftime('%d/%m/%Y')}"
    if not events:
        await context.bot.send_message(
            chat_id=TELEGRAM_ALLOWED_USER_ID,
            text=header + "\n\nHôm nay không có tin tức vĩ mô quan trọng.\nChúc bạn một ngày trade thật thành công nha!"
        )
        return
    lines = [header, "", "🧭 Lịch tin vĩ mô quan trọng:"]
    for e in events:
        tstr = e["time_vn"].strftime("%H:%M")
        extra = []
        if e.get("forecast"): extra.append(f"Dự báo {e['forecast']}")
        if e.get("previous"): extra.append(f"Trước {e['previous']}")
        extra_str = (" — " + ", ".join(extra)) if extra else ""
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

# ========= TÍNH ĐIỂM KHẨN =========
async def _calc_urgency_components(session, symbol: str):
    """
    Trả về: (ret15m_abs, z_vol, abs_funding, metrics)
    metrics: last, rsi, ema50, ema200, trend, vol_ratio, funding
    """
    m = await quick_signal_metrics(session, symbol, interval="5m")
    last = m.get("last") or 0.0
    ema9  = m.get("ema50") or last
    ema21 = m.get("ema200") or last
    if last:
        ret15m_abs = abs((ema9 - ema21) / last) * 100.0
    else:
        ret15m_abs = 0.0

    vol_ratio = m.get("vol_ratio") or 1.0
    z_vol = max(0.0, vol_ratio - 1.0)  # độ lệch trên MA
    abs_funding = abs(m.get("funding") or 0.0)
    return ret15m_abs, z_vol, abs_funding, m

def _urgent_score(ret15m_abs, z_vol, abs_funding):
    # trọng số: volume bất thường > biến động giá > funding lệch
    return 1.0 * z_vol + 0.6 * ret15m_abs + 40.0 * abs_funding

def _fmt_sticky_block(items):
    lines = ["🔴 BẢNG CẢNH BÁO KHẨN (Top score)"]
    for it in items:
        sym = it["symbol"]
        sc  = it["score"]
        m   = it["metrics"]
        arrow = "▲" if (m.get("vol_ratio") or 1.0) >= 1.8 else ""
        side_hint = "Long nghiêng" if (m.get("funding") or 0) > 0 else ("Short nghiêng" if (m.get("funding") or 0) < 0 else "Trung tính")
        lines.append(
            f"• {sym} | score {sc:.2f} | Vol5m x{(m.get('vol_ratio') or 1.0):.2f}{arrow} | Funding {m.get('funding',0):.4f} ({side_hint})"
        )
    lines.append("💡 Ưu tiên theo dõi top score; chờ ổn định 1–3 nến trước khi vào.")
    return "\n".join(lines)

# ========= 06:00→22:00 — 30' gửi 5 tín hiệu (gắn ⭐ nếu gần khẩn) =========
async def job_halfhour_signals(context: ContextTypes.DEFAULT_TYPE):
    if not _in_work_hours():
        return
    async with aiohttp.ClientSession() as session:
        syms = await active_symbols(session, min_quote_volume=MIN_QUOTE_VOL)
    if not syms:
        syms = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"]

    candidates = syms[:MAX_CANDIDATES]
    signals = await generate_batch(candidates, count=5)

    # Gắn sao ⭐ nếu gần mức khẩn
    async with aiohttp.ClientSession() as session:
        for i, s in enumerate(signals):
            s["signal_type"] = "Scalping" if i < 3 else "Swing"
            s["order_type"]  = "Market"

            star = ""
            try:
                ret15m_abs, z_vol, abs_funding, m = await _calc_urgency_components(session, s["token"])
                score = _urgent_score(ret15m_abs, z_vol, abs_funding)
                s["funding"]   = m.get("funding")
                s["vol_ratio"] = m.get("vol_ratio")
                if score >= STAR_SCORE_THRESHOLD:
                    star = "⭐ <b>Tín hiệu nổi bật</b>\n\n"
            except Exception:
                pass

            await context.bot.send_message(
                chat_id=TELEGRAM_ALLOWED_USER_ID,
                text=(star + _fmt_signal(s)),
                parse_mode="HTML"
            )
            bump_signals(1)

# ========= 06:00→22:00 — KHẨN (gộp 1 tin + pin mới, gỡ pin cũ hoặc sticky ảo) =========
async def job_urgent_alerts(context: ContextTypes.DEFAULT_TYPE):
    if not _in_work_hours():
        return
    if not can_alert_this_hour(ALERT_PER_HOUR_MAX):
        return

    async with aiohttp.ClientSession() as session:
        syms = await active_symbols(session, min_quote_volume=MIN_QUOTE_VOL)
        syms = syms[:MAX_CANDIDATES] if syms else ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"]

        scored = []
        for sym in syms:
            try:
                mq = await quick_signal_metrics(session, sym, interval="5m")
                vr = mq.get("vol_ratio") or 1.0
                fd = abs(mq.get("funding") or 0.0)
                if (fd < ALERT_FUNDING) and (vr < ALERT_VOLRATIO):
                    continue

                ret15m_abs, z_vol, abs_funding, m = await _calc_urgency_components(session, sym)
                score = _urgent_score(ret15m_abs, z_vol, abs_funding)
                if score < ALERT_SCORE_MIN:
                    continue

                strong = (score >= ALERT_SCORE_STRONG) or (vr >= ALERT_STRONG_VOLRATIO)
                if (not strong) and (not can_alert_symbol(sym, ALERT_COOLDOWN_MIN)):
                    continue

                scored.append({"symbol": sym, "score": score, "metrics": m, "strong": strong})
            except Exception:
                continue

        if not scored:
            return

        scored.sort(key=lambda x: x["score"], reverse=True)
        picks = scored[:min(ALERT_TOPK, ALERT_MAX_PER_RUN)]

        # Phần bảng cảnh báo
        board_lines = ["🔴 BẢNG CẢNH BÁO KHẨN (Top score)"]
        for it in picks:
            sym = it["symbol"]
            sc  = it["score"]
            m   = it["metrics"]
            arrow = "▲" if (m.get("vol_ratio") or 1.0) >= 1.8 else ""
            side_hint = "Long nghiêng" if (m.get("funding") or 0) > 0 else ("Short nghiêng" if (m.get("funding") or 0) < 0 else "Trung tính")
            board_lines.append(
                f"• {sym} | score {sc:.2f} | Vol5m x{(m.get('vol_ratio') or 1.0):.2f}{arrow} | Funding {m.get('funding',0):.4f} ({side_hint})"
            )
        board_lines.append("💡 Ưu tiên theo dõi top score; chờ ổn định 1–3 nến trước khi vào.")

        # Phần lệnh chi tiết
        detail_lines = ["", "⏰ TÍN HIỆU KHẨN (Chọn lọc)"]
        for it in picks:
            sym = it["symbol"]
            m   = it["metrics"]
            s   = await generate_signal(sym)
            s["signal_type"] = "Swing (Khẩn)"
            s["order_type"]  = "Market"
            s["funding"]     = m.get("funding")
            s["vol_ratio"]   = m.get("vol_ratio")

            side_hint = "Long nghiêng" if (m.get("funding") or 0) > 0 else ("Short nghiêng" if (m.get("funding") or 0) < 0 else "Trung tính")
            guidance = f"\n💡 Gợi ý: ưu tiên {'MUA' if s['side']=='LONG' else 'BÁN'} nếu ổn định thêm ({side_hint})."

            detail_lines.append("")
            detail_lines.append(_fmt_signal(s) + guidance)

            mark_alert_symbol(sym)
            bump_alerts(1)
            bump_alert_hour()

        combo_text = "\n".join(board_lines + detail_lines)

        # Gửi 1 tin duy nhất
        msg = await context.bot.send_message(
            chat_id=TELEGRAM_ALLOWED_USER_ID,
            text=combo_text,
            parse_mode="HTML"
        )

        # Pin mới + gỡ pin cũ (silent). Nếu không pin được (private), dùng sticky ảo.
        old_mid = get_sticky_message_id()
        pinned_ok = False
        if PIN_URGENT:
            try:
                await context.bot.pin_chat_message(
                    chat_id=TELEGRAM_ALLOWED_USER_ID,
                    message_id=msg.message_id,
                    disable_notification=True
                )
                pinned_ok = True
            except Exception:
                pinned_ok = False

        if pinned_ok:
            if old_mid and old_mid != msg.message_id:
                try:
                    await context.bot.unpin_chat_message(
                        chat_id=TELEGRAM_ALLOWED_USER_ID,
                        message_id=old_mid
                    )
                except Exception:
                    pass
            set_sticky_message_id(msg.message_id)
        else:
            try:
                if old_mid:
                    await context.bot.edit_message_text(
                        chat_id=TELEGRAM_ALLOWED_USER_ID,
                        message_id=old_mid,
                        text=combo_text
                    )
                else:
                    m2 = await context.bot.send_message(
                        chat_id=TELEGRAM_ALLOWED_USER_ID,
                        text=combo_text,
                        parse_mode="HTML"
                    )
                    set_sticky_message_id(m2.message_id)
            except Exception:
                pass

# ========= 22:00 — Tổng kết =========
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

# ========= ĐĂNG KÝ JOB =========
def setup_jobs(app: Application):
    jq = app.job_queue
    if jq is None:
        jq = JobQueue()
        jq.set_application(app)
        jq.start()
        app.job_queue = jq

    jq.run_daily(job_morning,       time=dt.time(hour=6,  minute=0, tzinfo=VN_TZ), name="morning_0600")
    jq.run_daily(job_macro,         time=dt.time(hour=7,  minute=0, tzinfo=VN_TZ), name="macro_0700")
    jq.run_repeating(job_halfhour_signals, interval=1800, first=5,  name="signals_30m")
    jq.run_repeating(job_urgent_alerts,    interval=600,  first=15, name="alerts_10m")  # 10 phút
    jq.run_daily(job_night_summary, time=dt.time(hour=22, minute=0, tzinfo=VN_TZ), name="summary_2200")
