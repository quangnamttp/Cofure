from dataclasses import dataclass
from cofure.macro.source import MacroItem

@dataclass
class ReleaseData:
    event: str
    actual: str | None = None
    forecast: str | None = None
    previous: str | None = None

def build_prealert(it: MacroItem) -> str:
    return f"⏳ {it.event} lúc {it.time} (Ảnh hưởng: High)\nLời khuyên: giảm rủi ro/đứng ngoài trước 5–15’."

def build_onrelease(it: MacroItem, data: ReleaseData | None = None) -> str:
    head = f"🕯️ {it.event} ({it.time})"
    body = "Đang cập nhật số liệu (bản rút gọn)."
    judge = "Nhận định: đánh giá phản ứng funding/biên độ 5–15’ sau tin, đi theo xu hướng nếu EMA 15m đồng thuận."
    return f"{head}\n{body}\n{judge}"

def build_followup(it: MacroItem) -> str:
    return (f"✅ Sau tin {it.event}\n"
            "Quan sát: funding BTC & biên độ 5’ hiện tại.\n"
            "Gợi ý: nếu xu hướng/EMA 15m đồng thuận → cân nhắc theo hướng vừa hình thành.")
