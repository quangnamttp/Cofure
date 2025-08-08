import asyncio
from fastapi import FastAPI
from cofure.bot import build_bot
from cofure.scheduler import schedule_all

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}

_application = None

@app.on_event("startup")
async def startup():
    global _application
    _application = build_bot()
    schedule_all(_application)
    asyncio.create_task(_application.run_polling())
