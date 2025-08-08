from dataclasses import dataclass
from typing import List
from cofure.utils.time import now_vn

@dataclass
class MacroItem:
    time: str   # HH:MM (giờ VN)
    event: str
    impact: str # Low | Medium | High
    note: str | None = None

async def load_today_items() -> List[MacroItem]:
    """
    Chế độ tự động an toàn (không cần API):
    - Trả về danh sách sự kiện mẫu, ổn định cho 07:00
    - Bản sau có thể thay bằng nguồn thật khi bạn yêu cầu
    """
    # Ví dụ mẫu ổn định (đủ cho format & lịch)
    return [
        MacroItem("19:30", "US CPI", "High", "Theo dõi 5–15’ đầu"),
        MacroItem("21:00", "FOMC Minutes", "High", "Đứng ngoài khi biến động cao"),
    ]
