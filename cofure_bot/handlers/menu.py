from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import pytz

from ..config import TELEGRAM_ALLOWED_USER_ID, TZ_NAME
from ..scheduler.jobs import (
    job_morning,
    job_macro,
    job_halfhour_signals,
    job_urgent_alerts,
    job_night_summary
)
from ..data.macro_calendar import fetch_macro_today, fetch_macro_week

VN_TZ = pytz.timezone(TZ_NAME)

# ====== Tạo menu chính ======
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != TELEGRAM_ALLOWED_USER_ID:
        return
    buttons = [
        [KeyboardButton("📅 Lịch hôm nay"), KeyboardButton("📅 Lịch ngày mai")],
        [KeyboardButton("📅 Lịch cả tuần")],
        [KeyboardButton("🧪 Test tất cả tính năng (6h→22h)")],
    ]
    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text("Chọn chức năng:", reply_markup=reply_markup)

# ====== Các nút menu ======
async def handle_menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text == "📅 Lịch hôm nay":
        events = await fetch_macro_today()
        now = datetime.now(VN_TZ)
        header = f"📅 Hôm nay là Thứ {now.isoweekday()}, ngày {now.strftime('%d/%m/%Y')}"
        if not events:
            await update.message.reply_text(header + "\n\nHôm nay không có tin tức vĩ mô quan trọng.")
        else:
            lines = [header, "", "🧭 Lịch tin vĩ mô quan trọng:"]
            for e in events:
                tstr = e["time_vn"].strftime("%H:%M")
                extra = []
                if e.get("forecast"): extra.append(f"Dự báo {e['forecast']}")
                if e.get("previous"): extra.append(f"Trước {e['previous']}")
                extra_str = (" — " + ", ".join(extra)) if extra else ""
                lines.append(f"• {tstr} — {e['title_vi']} — Ảnh hưởng: {e['impact']}{extra_str}")
            await update.message.reply_text("\n".join(lines))

    elif text == "📅 Lịch ngày mai":
        tomorrow = datetime.now(VN_TZ) + timedelta(days=1)
        events = await fetch_macro_today(tomorrow)
        header = f"📅 Ngày mai: {tomorrow.strftime('%d/%m/%Y')}"
        if not events:
            await update.message.reply_text(header + "\n\nKhông có tin tức vĩ mô quan trọng.")
        else:
            lines = [header, "", "🧭 Lịch tin vĩ mô quan trọng:"]
            for e in events:
                tstr = e["time_vn"].strftime("%H:%M")
                lines.append(f"• {tstr} — {e['title_vi']} — Ảnh hưởng: {e['impact']}")
            await update.message.reply_text("\n".join(lines))

    elif text == "📅 Lịch cả tuần":
        week_events = await fetch_macro_week()
        if not week_events:
            await update.message.reply_text("Không có dữ liệu lịch cả tuần.")
        else:
            lines = ["📅 Lịch cả tuần:"]
            for day, events in week_events.items():
                lines.append(f"\n=== {day} ===")
                for e in events:
                    tstr = e["time_vn"].strftime("%H:%M")
                    lines.append(f"• {tstr} — {e['title_vi']} — {e['impact']}")
            await update.message.reply_text("\n".join(lines))

    elif text == "🧪 Test tất cả tính năng (6h→22h)":
        await update.message.reply_text("🔄 Đang test tất cả tính năng...")
        await job_morning(context)
        await job_macro(context)
        await job_halfhour_signals(context)
        await job_urgent_alerts(context)
        await job_night_summary(context)

    else:
        await update.message.reply_text("❓ Không hiểu lệnh, vui lòng chọn từ menu.")
