import asyncio
import logging
import sys
from aiohttp import web
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters
from .config import APP_NAME, PORT, TELEGRAM_BOT_TOKEN, PUBLIC_BASE_URL
from .handlers.commands import start, on_text
from .scheduler.jobs import setup_jobs  # job 30'

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
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    await application.initialize()
    await application.start()

    webhook_url = f"{PUBLIC_BASE_URL.rstrip('/')}/webhook"  # tránh //webhook
    await application.bot.set_webhook(webhook_url)
    logger.info("Webhook set to %s", webhook_url)
    return application

async def main():
    # Khởi động Telegram (webhook)
    application = await _start_telegram_webhook()

    # Đăng ký lịch gửi tín hiệu 30'
    setup_jobs(application)

    # Khởi động web server aiohttp (health + webhook)
    runner = await _start_aiohttp(application)

    try:
        await asyncio.Event().wait()
    finally:
        await application.stop()
        await application.shutdown()
        await runner.cleanup()
