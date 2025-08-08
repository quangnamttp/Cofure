import os
from pydantic import BaseModel

class Settings(BaseModel):
    telegram_token: str
    telegram_chat_id: str
    tz: str = "Asia/Ho_Chi_Minh"

def get_settings() -> Settings:
    return Settings(
        telegram_token=os.environ["TELEGRAM_TOKEN"],
        telegram_chat_id=os.environ["TELEGRAM_CHAT_ID"],
        tz=os.environ.get("TZ", "Asia/Ho_Chi_Minh"),
    )
