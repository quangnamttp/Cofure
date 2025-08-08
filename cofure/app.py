# cofure/app.py
import asyncio
import logging
from fastapi import FastAPI
from cofure.bot import build_bot
from cofure.scheduler import schedule_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("cofure")

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/")
def home():
    return {"message": "Cofure bot is running!"}

_application = None
_polling_task: asyncio.Task | None = None

@app.on_event("startup")
async def startup():
    global _application, _polling_task
    log.info("Starting Cofure app…")

    _application = build_bot()              # tạo Application (PTB)
    log.info("Telegram bot built")

    schedule_all(_application)              # gắn scheduler
    log.info("Scheduler initialized")

    # QUAN TRỌNG: chạy polling ở background + không đóng event loop
    _polling_task = asyncio.create_task(
        _application.run_polling(close_loop=False)
    )
    log.info("Bot polling started")

@app.on_event("shutdown")
async def shutdown():
    global _polling_task
    log.info("Shutting down Cofure app…")
    try:
        if _polling_task and not _polling_task.done():
            _polling_task.cancel()
            try:
                await _polling_task
            except asyncio.CancelledError:
                pass
        log.info("Polling task stopped")
    except Exception as e:
        log.exception(f"Error during shutdown: {e}")
    log.info("Cofure app stopped")
