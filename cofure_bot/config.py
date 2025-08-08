import os

APP_NAME = "Cofure"
TZ_NAME = os.getenv("TZ", "Asia/Ho_Chi_Minh")

# Server / Render
PORT = int(os.getenv("PORT", "10000"))  # Render sẽ set PORT tự động
ENV = os.getenv("ENV", "production")
VERSION = os.getenv("VERSION", "v1.0.0-branch2")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALLOWED_USER_ID = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://cofure.onrender.com")
