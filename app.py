import logging
import sys
from aiohttp import web
from cofure_bot.config import PORT, APP_NAME, ENV, VERSION
from cofure_bot.utils.time import fmt

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(APP_NAME)

async def health(request):
    # Endpoint cho UptimeRobot/Render health checks
    return web.json_response({
        "status": "ok",
        "app": APP_NAME,
        "env": ENV,
        "version": VERSION,
        "time": fmt()
    })

async def info(request):
    return web.Response(
        text=f"{APP_NAME} {VERSION} — {ENV} — {fmt()}",
        content_type="text/plain"
    )

async def init_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/info", info)
    return app

def main():
    web.run_app(init_app(), host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
