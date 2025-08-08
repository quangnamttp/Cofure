import asyncio
import logging
import sys
from aiohttp import web
from telegram import Update, BotCommand
from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters
from .config import APP_NAME, PORT, TELEGRAM_BOT_TOKEN, PUBLIC_BASE_URL
from .handlers.commands import start, on_text
from .handlers.menu import (
    lich_hom_nay_cmd, lich_ngay_mai_cmd, lich_ca_tuan_cmd, test_full_cmd
)
from .scheduler.jobs import setup_jobs  # job 30' + jobs theo giờ

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(APP_NAME)

# -------- AIOHTTP (endpoints) --------
async def index(request):
    return web.json_response({"status": "ok", "app": APP_NAME})

async def health(request):
    return web.json_response({"status": "ok", "app": APP_NAME})

async def info(request):
    return web.Response(text=f"{APP_NAME} is running", content_type="text/plain")

async def webhook_handler(request):
    data = await request.json()
    application: Application = request.app["application"]
    update = Update.de_json(data, application.bot)
    await application.update_queue.put(update)
    return web.Response(status=200)

async def _start_aiohttp(application: Application):
    app = web.Application()
    app["application"] = application
    app.router.add_get("/", index)
    app.router.add_get("/health", health)
    app.router.add_get("/info", info)
    app.router.add_post("/webhook", webhook_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    return runner

# -------- Telegram (WEBHOOK) --------
async def _start_telegram_webhook() -> Application:
    application: Application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers cơ bản
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # Handlers menu (lịch + test full)
    application.add_handler(CommandHandler("lich_hom_nay", lich_hom_nay_cmd))
    application.add_handler(CommandHandler("lich_ngay_mai", lich_ngay_mai_cmd))
    application.add_handler(CommandHandler("lich_ca_tuan", lich_ca_tuan_cmd))
    application.add_handler(CommandHandler("test_full", test_full_cmd))

    await application.initialize()
    await application.start()

    # Đăng ký menu lệnh hiển thị trong Telegram
    await application.bot.set_my_commands([
        BotCommand("lich_hom_nay", "📅 Tin vĩ mô hôm nay"),
        BotCommand("lich_ngay_mai", "📅 Tin vĩ mô ngày mai"),
        BotCommand("lich_ca_tuan", "📅 Lịch từ Thứ 2 đến Chủ nhật"),
        BotCommand("test_full", "🧪 Test đầy đủ 06:00→22:00"),
    ])

    webhook_url = f"{PUBLIC_BASE_URL.rstrip('/')}/webhook"  # tránh //webhook
    await application.bot.set_webhook(webhook_url)
    logger.info("Webhook set to %s", webhook_url)
    return application

async def main():
    # Khởi động Telegram (webhook)
    application = await _start_telegram_webhook()

    # Đăng ký các job theo giờ + tín hiệu 30'
    setup_jobs(application)

    # Khởi động web server aiohttp (health + webhook)
    runner = await _start_aiohttp(application)

    try:
        await asyncio.Event().wait()
    finally:
        await application.stop()
        await application.shutdown()
        await runner.cleanup()
