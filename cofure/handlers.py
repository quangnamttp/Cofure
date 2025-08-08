from telegram import Update
from telegram.ext import ContextTypes
from cofure.utils.time import fmt_vn
from cofure.macro.calendar_router import get_calendar_text

async def cmd_ping(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Pong! {fmt_vn()}")

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cofure đang ON • 06:00/07:00/chu kỳ 30’ • Tổng kết 22:00")

async def handle_lich_keywords(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").lower().strip()
    if "cả tuần" in text:
        mode = "week"
    elif "ngày mai" in text:
        mode = "tomorrow"
    else:
        mode = "today"
    msg = await get_calendar_text(mode)
    await update.message.reply_text(msg)
