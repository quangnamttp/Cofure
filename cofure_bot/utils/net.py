import asyncio
from typing import Callable, TypeVar

T = TypeVar("T")

def with_retry(max_attempts: int = 3, base_delay: float = 0.8):
    """
    Decorator: retry nhẹ với backoff khi call API lỗi (network/5xx).
    """
    def deco(fn: Callable[..., T]):
        async def wrapper(*args, **kwargs):
            attempt = 1
            while True:
                try:
                    return await fn(*args, **kwargs)
                except Exception as e:
                    if attempt >= max_attempts:
                        raise
                    await asyncio.sleep(base_delay * attempt)
                    attempt += 1
        return wrapper
    return deco
