from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from cofure.config import get_settings
from cofure.handlers import cmd_status, cmd_ping, handle_lich_keywords

def build_bot():
    s = get_settings()
    app = ApplicationBuilder().token(s.telegram_token).build()
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("status", cmd_status))
    # Từ khóa: "lịch hôm nay" | "lịch ngày mai" | "lịch cả tuần"
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^lịch( hôm nay| ngày mai| cả tuần)?$"), handle_lich_keywords))
    return app
