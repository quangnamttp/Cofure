from telegram import Update
from telegram.ext import ContextTypes
from ..config import TELEGRAM_ALLOWED_USER_ID

def _authorized(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id == TELEGRAM_ALLOWED_USER_ID)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return
    await update.message.reply_text(
        "Xin chào! Cofure đã sẵn sàng.\n"
        "Từ khóa nhanh: lịch hôm nay | lịch ngày mai | lịch cả tuần"
    )

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return
    text = (update.message.text or "").strip().lower()
    if text in {"lịch hôm nay", "lịch ngày mai", "lịch cả tuần"}:
        await update.message.reply_text("Tính năng lịch sẽ hoạt động ở các nhánh tiếp theo 👌")
        return
    await update.message.reply_text("Đã nhận. Gõ: lịch hôm nay | lịch ngày mai | lịch cả tuần")
