# cofure/bot.py
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")   # Lấy token từ biến môi trường
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Chat ID của bạn

def build_bot() -> Application:
    app = Application.builder().token(TOKEN).build()

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Xin chào! Bot Cofure đã sẵn sàng 🚀")

    async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Pong! ✅")

    async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Bot đang hoạt động 🔥")

    # Thêm các lệnh cơ bản
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("status", status))

    return app
