# cofure_bot/scheduler/jobs.py

import aiohttp
import datetime as dt
from datetime import datetime, timedelta
from telegram.ext import Application, ContextTypes, JobQueue
import pytz

from cofure_bot.config import TELEGRAM_ALLOWED_USER_ID, TZ_NAME
from cofure_bot.signals.engine import generate_batch, generate_signal
from cofure_bot.data.binance_client import active_symbols, top_gainers, quick_signal_metrics
from cofure_bot.data.macro_calendar import fetch_macro_today, fetch_macro_week
from cofure_bot.storage.state import (
    bump_signals, bump_alerts, snapshot,
    can_alert_symbol, mark_alert_symbol,
    can_alert_this_hour, bump_alert_hour,
    get_sticky_message_id, set_sticky_message_id,
)

VN_TZ = pytz.timezone(TZ_NAME)

# ========= NGƯỠNG & CẤU HÌNH =========
MIN_QUOTE_VOL   = 5_000_000.0
MAX_CANDIDATES  = 60

WORK_START      = 6
WORK_END        = 22

ALERT_FUNDING   = 0.02
ALERT_VOLRATIO  = 1.8

ALERT_COOLDOWN_MIN   = 180
ALERT_TOPK           = 2
ALERT_MAX_PER_RUN    = 3
ALERT_SCORE_MIN      = 3.0
ALERT_PER_HOUR_MAX   = 3
PIN_URGENT           = True

ALERT_STRONG_VOLRATIO = 3.0
ALERT_SCORE_STRONG    = 6.0

STAR_SCORE_THRESHOLD  = 5.0

# ====== CACHE đơn giản cho phân tích lịch ======
_pre_announced = set()   # id + marker từng mốc (id@-30, id@-15, id@-05)
_post_reported  = set()   # id đã báo sau tin

# ========= TIỆN ÍCH =========
def _in_work_hours() -> bool:
    now = datetime.now(VN_TZ)
    return WORK_START <= now.hour < WORK_END

def _day_name_vi(d: datetime) -> str:
    return {1:"Thứ 2",2:"Thứ 3",3:"Thứ 4",4:"Thứ 5",5:"Thứ 6",6:"Thứ 7",7:"Chủ nhật"}[d.isoweekday()]

def _fmt_signal(sig: dict) -> str:
    label = "Mạnh" if sig["strength"] >= 70 else ("Tiêu chuẩn" if sig["strength"] >= 50 else "Tham khảo")
    side_square = "🟩" if sig["side"] == "LONG" else "🟥"
    reasons = []
    if "funding" in sig and sig["funding"] is not None: reasons.append(f"Funding={sig['funding']:.4f}")
    if "vol_ratio" in sig and sig["vol_ratio"] is not None: reasons.append(f"Vol5m=x{sig['vol_ratio']:.2f}")
    if sig.get("rsi") is not None: reasons.append(f"RSI={sig['rsi']}")
    if sig.get("ema9") is not None: reasons.append(f"EMA9={sig['ema9']}")
    if sig.get("ema21") is not None: reasons.append(f"EMA21={sig['ema21']}")
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

# ====== Heuristic bias theo loại tin ======
def _macro_bias(event_title_en: str, actual: str, forecast: str, previous: str) -> str:
    """
    Trả về gợi ý bias chung cho crypto (risk-on/risk-off).
    - CPI/PCE/PPI: actual < forecast -> risk-on; > forecast -> risk-off
    - Unemployment: actual > forecast -> risk-off
    - NFP: actual >> forecast -> risk-on (độ mạnh kinh tế), nhưng nếu quá “nóng” có thể risk-off do Fed hawkish (đơn giản hoá: > forecast chút: on; quá cao > forecast*1.3: off)
    - Rate/FOMC: 'cut' gợi on (tuỳ bối cảnh), 'hike' gợi off; nếu “hold” nhìn dot plot/statement (không có ở feed) => neutral
    """
    t = (event_title_en or "").lower()
    def num(x):
       try: 
           return float(str(x).replace('%','').replace(',','').strip())
       except: 
           return None

    a, f, p = num(actual), num(forecast), num(previous)

    if "cpi" in t or "pce" in t or "ppi" in t or "inflation" in t:
        if a is not None and f is not None:
            return "✅ Risk-on (lạm phát thấp hơn dự báo)" if a < f else "⚠️ Risk-off (lạm phát cao hơn dự báo)"
        return "ℹ️ Theo dõi lạm phát: thấp → on, cao → off"

    if "unemployment" in t or "jobless" in t:
        if a is not None and f is not None:
            return "⚠️ Risk-off (thất nghiệp cao hơn dự báo)" if a > f else "✅ Risk-on (thất nghiệp thấp hơn dự báo)"
        return "ℹ️ Theo dõi thất nghiệp: cao → off, thấp → on"

    if "non-farm" in t or "nfp" in t or "payrolls" in t:
        if a is not None and f is not None:
            if a > 1.3 * f:
                return "⚠️ Có thể Risk-off (quá nóng → Fed hawkish)"
            elif a > f:
                return "✅ Hơi Risk-on (việc làm tốt hơn dự báo)"
            else:
                return "⚠️ Hơi Risk-off (việc làm kém)"
        return "ℹ️ Theo dõi NFP: tốt vừa → on, quá nóng → off"

    if "interest rate" in t or "fomc" in t or "rate decision" in t or "fed" in t:
        if actual:
            at = actual.lower()
            if "cut" in at:
                return "✅ Nghiêng Risk-on (cắt lãi)"
            if "hike" in at or "+" in at:
                return "⚠️ Nghiêng Risk-off (tăng lãi)"
            if "hold" in at or at == previous:
                return "ℹ️ Trung tính (giữ nguyên)"
        return "ℹ️ Chờ chi tiết quyết định & họp báo"

    if "retail sales" in t or "pmi" in t or "ism" in t or "gdp" in t:
        if a is not None and f is not None:
            return "✅ Risk-on (số liệu tốt hơn)" if a > f else "⚠️ Risk-off (số liệu xấu hơn)"
        return "ℹ️ Số liệu tốt → on, xấu → off"

    return "ℹ️ Sự kiện vĩ mô quan trọng — phản ứng tuỳ bối cảnh"

# ========= 06:00 — Chào buổi sáng =========
async def job_morning(context: ContextTypes.DEFAULT_TYPE):
    usd_vnd = None
    try:
        async with aiohttp.ClientSession() as s:
            try:
                async with s.get("https://api.exchangerate.host/latest",
                                 params={"base":"USD","symbols":"VND"},
                                 timeout=aiohttp.ClientTimeout(total=10)) as r:
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

    lines = [f"Chào buổi sáng nhé Cofure ☀️  (1 USD ≈ {usd_vnd:,.0f} VND)" if usd_vnd else
             "Chào buổi sáng nhé Cofure ☀️  (USD≈VND - tham chiếu)", ""]
    lines.append("🔥 5 đồng tăng trưởng nổi bật (24h):")
    for g in gainers:
        sym = g.get("symbol"); chg = float(g.get("priceChangePercent", 0) or 0); vol = float(g.get("quoteVolume", 0) or 0)
        lines.append(f"• <b>{sym}</b> ▲ {chg:.2f}% | Volume: {vol:,.0f} USDT")
    lines += ["", "📊 Funding, volume, xu hướng sẽ có trong tín hiệu định kỳ suốt ngày."]

    await context.bot.send_message(chat_id=TELEGRAM_ALLOWED_USER_ID,
                                   text="\n".join(lines), parse_mode="HTML",
                                   disable_web_page_preview=True)

# ========= 07:00 — Lịch vĩ mô hôm nay =========
async def job_macro(context: ContextTypes.DEFAULT_TYPE):
    events = await fetch_macro_today()
    now = datetime.now(VN_TZ)
    header = f"📅 {_day_name_vi(now)}, ngày {now.strftime('%d/%m/%Y')}"
    if not events:
        await context.bot.send_message(chat_id=TELEGRAM_ALLOWED_USER_ID,
                                       text=header + "\n\nHôm nay không có tin tức vĩ mô quan trọng.\nChúc bạn một ngày trade thật thành công nha!")
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
            h = int(left.total_seconds() // 3600); m = int((left.total_seconds() % 3600)//60)
            countdown = f" — ⏳ còn {h} giờ {m} phút" if h else f" — ⏳ còn {m} phút"
        else:
            countdown = ""
        lines.append(f"• {tstr} — {e['title_vi']} — Ảnh hưởng: {e['impact']}{extra_str}{countdown}")
    lines.append("\n💡 Gợi ý: Đứng ngoài 5–10’ quanh giờ ra tin; quan sát funding/volume.")
    await context.bot.send_message(chat_id=TELEGRAM_ALLOWED_USER_ID, text="\n".join(lines))

# ========= TÍNH ĐIỂM KHẨN =========
async def _calc_urgency_components(session, symbol: str):
    m = await quick_signal_metrics(session, symbol, interval="5m")
    last = m.get("last") or 0.0
    ema9  = m.get("ema50") or last
    ema21 = m.get("ema200") or last
    ret15m_abs = abs((ema9 - ema21) / last) * 100.0 if last else 0.0
    vol_ratio = m.get("vol_ratio") or 1.0
    z_vol = max(0.0, vol_ratio - 1.0)
    abs_funding = abs(m.get("funding") or 0.0)
    return ret15m_abs, z_vol, abs_funding, m

def _urgent_score(ret15m_abs, z_vol, abs_funding):
    return 1.0 * z_vol + 0.6 * ret15m_abs + 40.0 * abs_funding

def _fmt_board(picks):
    lines = ["🔴 BẢNG CẢNH BÁO KHẨN (Top score)"]
    for it in picks:
        sym = it["symbol"]; sc = it["score"]; m = it["metrics"]
        arrow = "▲" if (m.get("vol_ratio") or 1.0) >= 1.8 else ""
        side_hint = "Long nghiêng" if (m.get("funding") or 0) > 0 else ("Short nghiêng" if (m.get("funding") or 0) < 0 else "Trung tính")
        lines.append(f"• {sym} | score {sc:.2f} | Vol5m x{(m.get('vol_ratio') or 1.0):.2f}{arrow} | Funding {m.get('funding',0):.4f} ({side_hint})")
    lines.append("💡 Ưu tiên theo dõi top score; chờ ổn định 1–3 nến trước khi vào.")
    return "\n".join(lines)

# ========= 30' gửi 5 tín hiệu (gắn ⭐ nếu gần khẩn) =========
async def job_halfhour_signals(context: ContextTypes.DEFAULT_TYPE):
    if not _in_work_hours():
        return
    async with aiohttp.ClientSession() as session:
        syms = await active_symbols(session, min_quote_volume=MIN_QUOTE_VOL)
    if not syms: syms = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"]

    candidates = syms[:MAX_CANDIDATES]
    signals = await generate_batch(candidates, count=5)

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
            await context.bot.send_message(chat_id=TELEGRAM_ALLOWED_USER_ID,
                                           text=(star + _fmt_signal(s)),
                                           parse_mode="HTML")
            bump_signals(1)

# ========= KHẨN (gộp 1 tin + pin/unpin + sticky ảo) =========
async def job_urgent_alerts(context: ContextTypes.DEFAULT_TYPE):
    if not _in_work_hours(): return
    if not can_alert_this_hour(ALERT_PER_HOUR_MAX): return

    async with aiohttp.ClientSession() as session:
        syms = await active_symbols(session, min_quote_volume=MIN_QUOTE_VOL)
        syms = syms[:MAX_CANDIDATES] if syms else ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"]

        scored = []
        for sym in syms:
            try:
                mq = await quick_signal_metrics(session, sym, interval="5m")
                vr = mq.get("vol_ratio") or 1.0
                fd = abs(mq.get("funding") or 0.0)
                if (fd < ALERT_FUNDING) and (vr < ALERT_VOLRATIO): continue

                ret15m_abs, z_vol, abs_funding, m = await _calc_urgency_components(session, sym)
                score = _urgent_score(ret15m_abs, z_vol, abs_funding)
                if score < ALERT_SCORE_MIN: continue

                strong = (score >= ALERT_SCORE_STRONG) or (vr >= ALERT_STRONG_VOLRATIO)
                if (not strong) and (not can_alert_symbol(sym, ALERT_COOLDOWN_MIN)): continue

                scored.append({"symbol": sym, "score": score, "metrics": m, "strong": strong})
            except Exception:
                continue

        if not scored: return
        scored.sort(key=lambda x: x["score"], reverse=True)
        picks = scored[:min(ALERT_TOPK, ALERT_MAX_PER_RUN)]

        board = _fmt_board(picks)
        detail = ["", "⏰ TÍN HIỆU KHẨN (Chọn lọc)"]
        for it in picks:
            sym = it["symbol"]; m = it["metrics"]
            s = await generate_signal(sym)
            s["signal_type"] = "Swing (Khẩn)"; s["order_type"] = "Market"
            s["funding"] = m.get("funding"); s["vol_ratio"] = m.get("vol_ratio")
            side_hint = "Long nghiêng" if (m.get("funding") or 0) > 0 else ("Short nghiêng" if (m.get("funding") or 0) < 0 else "Trung tính")
            guidance = f"\n💡 Gợi ý: ưu tiên {'MUA' if s['side']=='LONG' else 'BÁN'} nếu ổn định thêm ({side_hint})."
            detail += ["", _fmt_signal(s) + guidance]
            mark_alert_symbol(sym); bump_alerts(1); bump_alert_hour()

        combo_text = "\n".join([board] + detail)

        msg = await context.bot.send_message(chat_id=TELEGRAM_ALLOWED_USER_ID, text=combo_text, parse_mode="HTML")

        old_mid = get_sticky_message_id(); pinned_ok = False
        if PIN_URGENT:
            try:
                await context.bot.pin_chat_message(chat_id=TELEGRAM_ALLOWED_USER_ID, message_id=msg.message_id, disable_notification=True)
                pinned_ok = True
            except Exception:
                pinned_ok = False

        if pinned_ok:
            if old_mid and old_mid != msg.message_id:
                try: await context.bot.unpin_chat_message(chat_id=TELEGRAM_ALLOWED_USER_ID, message_id=old_mid)
                except Exception: pass
            set_sticky_message_id(msg.message_id)
        else:
            try:
                if old_mid:
                    await context.bot.edit_message_text(chat_id=TELEGRAM_ALLOWED_USER_ID, message_id=old_mid, text=combo_text)
                else:
                    m2 = await context.bot.send_message(chat_id=TELEGRAM_ALLOWED_USER_ID, text=combo_text, parse_mode="HTML")
                    set_sticky_message_id(m2.message_id)
            except Exception:
                pass

# ========= PHÂN TÍCH LÚC RA TIN — TRƯỚC GIỜ =========
async def job_macro_watch_pre(context: ContextTypes.DEFAULT_TYPE):
    """Báo trước giờ ra tin 30', 15', 5' + snapshot BTC/ETH."""
    events = await fetch_macro_week()
    if not events: return
    now = datetime.now(VN_TZ)

    # mốc cảnh báo (phải trùng gần chính xác để không spam)
    checkpoints = [30, 15, 5]  # phút
    targets = []
    for e in events:
        # chỉ nhắc sự kiện High hoặc có từ khoá IMPORTANT (đã lọc ở fetch)
        delta_min = int((e["time_vn"] - now).total_seconds() // 60)
        for cp in checkpoints:
            if delta_min == cp:
                key = f"{e['id']}@-{cp}"
                if key not in _pre_announced:
                    targets.append((e, cp, key))

    if not targets: return

    async with aiohttp.ClientSession() as session:
        def fmt_snap(sym, m):
            return f"{sym}: funding {m.get('funding',0):.4f} | Vol5m x{(m.get('vol_ratio') or 1.0):.2f}"

        for e, cp, key in targets:
            try:
                btc = await quick_signal_metrics(session, "BTCUSDT", interval="5m")
                eth = await quick_signal_metrics(session, "ETHUSDT", interval="5m")
            except Exception:
                btc = {}; eth = {}
            # gợi ý bias sơ bộ (chưa có actual)
            bias = _macro_bias(e.get("title") or "", e.get("actual") or "", e.get("forecast") or "", e.get("previous") or "")

            lines = [
                f"⏳ {cp} phút nữa ra tin: <b>{e['title_vi']}</b>",
                f"🕒 Giờ VN: {e['time_vn'].strftime('%H:%M %d/%m')}",
                f"📊 Ảnh hưởng: {e['impact']}",
            ]
            extra = []
            if e.get("forecast"): extra.append(f"Dự báo: {e['forecast']}")
            if e.get("previous"): extra.append(f"Trước: {e['previous']}")
            if extra: lines.append(" — ".join(extra))
            lines += [
                "",
                "📈 Snapshot thị trường:",
                f"• {fmt_snap('BTC', btc)}",
                f"• {fmt_snap('ETH', eth)}",
                "",
                f"🧭 Bias sơ bộ: {bias}",
                "💡 Mẹo: Đứng ngoài 5–10’ quanh giờ ra tin; tránh FOMO nến đầu."
            ]
            await context.bot.send_message(chat_id=TELEGRAM_ALLOWED_USER_ID, text="\n".join(lines), parse_mode="HTML")
            _pre_announced.add(key)

# ========= PHÂN TÍCH LÚC RA TIN — SAU GIỜ =========
async def job_macro_watch_post(context: ContextTypes.DEFAULT_TYPE):
    """Sau tin (≤15’), nếu có 'actual' thì so sánh Actual vs Forecast/Previous + snapshot BTC/ETH + bias."""
    events = await fetch_macro_week()
    if not events: return
    now = datetime.now(VN_TZ)

    candidates = []
    for e in events:
        dt = e["time_vn"]
        if 0 <= (now - dt).total_seconds() <= 15*60:  # trong 15 phút sau tin
            if e.get("actual"):
                if e["id"] not in _post_reported:
                    candidates.append(e)

    if not candidates: return

    async with aiohttp.ClientSession() as session:
        for e in candidates:
            try:
                btc = await quick_signal_metrics(session, "BTCUSDT", interval="5m")
                eth = await quick_signal_metrics(session, "ETHUSDT", interval="5m")
            except Exception:
                btc = {}; eth = {}

            bias = _macro_bias(e.get("title") or "", e.get("actual") or "", e.get("forecast") or "", e.get("previous") or "")

            lines = [
                f"🛎️ <b>Kết quả vừa công bố:</b> {e['title_vi']}",
                f"🕒 Giờ VN: {e['time_vn'].strftime('%H:%M %d/%m')}",
                f"📊 Ảnh hưởng: {e['impact']}",
            ]
            trio = []
            if e.get("actual"): trio.append(f"Thực tế: {e['actual']}")
            if e.get("forecast"): trio.append(f"Dự báo: {e['forecast']}")
            if e.get("previous"): trio.append(f"Trước: {e['previous']}")
            if trio: lines.append(" — ".join(trio))

            def fmt_snap(sym, m):
                return f"{sym}: funding {m.get('funding',0):.4f} | Vol5m x{(m.get('vol_ratio') or 1.0):.2f}"

            lines += [
                "",
                "📈 Snapshot sau tin:",
                f"• {fmt_snap('BTC', btc)}",
                f"• {fmt_snap('ETH', eth)}",
                "",
                f"🧭 Đánh giá: {bias}",
                "⚠️ Lưu ý: Nến đầu sau tin thường nhiễu; chờ xác nhận 1–3 nến."
            ]
            await context.bot.send_message(chat_id=TELEGRAM_ALLOWED_USER_ID, text="\n".join(lines), parse_mode="HTML")
            _post_reported.add(e["id"])

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

    # Tin khẩn: 10 phút/lần (đã có cooldown 3h/coin + cap 3 tin/giờ)
    jq.run_repeating(job_urgent_alerts,    interval=600,  first=15, name="alerts_10m")

    # Phân tích lịch: 5 phút/lần
    jq.run_repeating(job_macro_watch_pre,  interval=300,  first=20, name="macro_pre_5m")
    jq.run_repeating(job_macro_watch_post, interval=300,  first=50, name="macro_post_5m")

    jq.run_daily(job_night_summary, time=dt.time(hour=22, minute=0, tzinfo=VN_TZ), name="summary_2200")
