import asyncio
import logging
import sys
from aiohttp import web
from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters
from .config import APP_NAME, PORT, TELEGRAM_BOT_TOKEN
from .handlers.commands import start, on_text

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(APP_NAME)

# -------- AIOHTTP (health endpoints) --------
async def health(request):
    return web.json_response({"status": "ok", "app": APP_NAME})

async def info(request):
    return web.Response(text=f"{APP_NAME} is running", content_type="text/plain")

async def _start_aiohttp():
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/info", info)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    return runner

# -------- Telegram (long polling) --------
async def _start_telegram():
    application: Application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Application.ALL_UPDATE_TYPES)
    return application

async def main():
    runner = await _start_aiohttp()
    application = await _start_telegram()

    try:
        await asyncio.Event().wait()  # giữ tiến trình 24/7
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        await runner.cleanup()
