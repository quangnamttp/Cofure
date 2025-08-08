import os

APP_NAME = "Cofure"
TZ_NAME = os.getenv("TZ", "Asia/Ho_Chi_Minh")

# Server / Render
PORT = int(os.getenv("PORT", "10000"))
ENV = os.getenv("ENV", "production")
VERSION = os.getenv("VERSION", "v1.0.0-branch5")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALLOWED_USER_ID = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://cofure.onrender.com")

# Macro calendar (nếu có proxy JSON; không có cũng chạy bình thường)
MACRO_ENDPOINT = os.getenv("MACRO_ENDPOINT", "")
