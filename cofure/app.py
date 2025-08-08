# cofure/app.py
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

# NEW: root route để khỏi 404 khi mở trang chủ
@app.get("/")
def home():
    return {"message": "Cofure bot is running!"}

_application = None  # telegram Application

@app.on_event("startup")
async def startup():
    global _application
    log.info("Starting Cofure app…")

    _application = build_bot()
    log.info("Telegram bot built")

    # Lịch cron (06:00 / 06:55 / 07:00 / mỗi 30' / 22:00)
    schedule_all(_application)
    log.info("Scheduler initialized")

    # Không dùng run_polling để tránh chiếm/đóng event loop của uvicorn
    await _application.initialize()
    await _application.start()
    log.info("Telegram application started")

@app.on_event("shutdown")
async def shutdown():
    global _application
    log.info("Shutting down Cofure app…")
    try:
        if _application:
            await _application.stop()
            await _application.shutdown()
            log.info("Telegram application stopped")
    except Exception as e:
        log.exception(f"Error during shutdown: {e}")
    log.info("Cofure app stopped")
