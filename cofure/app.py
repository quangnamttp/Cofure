# cofure/app.py
import asyncio
import logging
from fastapi import FastAPI
from cofure.bot import build_bot
from cofure.scheduler import schedule_all

# ===== Logging setup =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("cofure")

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}

_application = None
_polling_task: asyncio.Task | None = None

@app.on_event("startup")
async def startup():
    global _application, _polling_task
    log.info("Starting Cofure app…")

    # Build Telegram bot
    _application = build_bot()
    log.info("Telegram bot built")

    # Schedule jobs
    schedule_all(_application)
    log.info("Scheduler initialized")

    # Run polling in background (fix event loop error)
    _polling_task = asyncio.create_task(
        _application.run_polling(close_loop=False)
    )
    log.info("Bot polling started in background")

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
