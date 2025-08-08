import os

APP_NAME = "Cofure"
TZ_NAME = os.getenv("TZ", "Asia/Ho_Chi_Minh")

# Server / Render
PORT = int(os.getenv("PORT", "10000"))  # Render sẽ set PORT tự động
ENV = os.getenv("ENV", "production")
VERSION = os.getenv("VERSION", "v1.0.0-branch1")
