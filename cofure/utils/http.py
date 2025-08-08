import httpx
from contextlib import asynccontextmanager

DEFAULT_TIMEOUT = httpx.Timeout(15.0, read=20.0)

@asynccontextmanager
async def client():
    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": "CofureBot/1.0 (+https://onrender.com)"}
    ) as c:
        yield c
