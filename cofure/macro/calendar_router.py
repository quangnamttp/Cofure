from datetime import timedelta
from cofure.macro.source import load_today_items
from cofure.utils.time import now_vn

async def get_calendar_text(mode: str = "today") -> str:
    today = now_vn()
    if mode == "tomorrow":
        head = f"📅 Ngày mai, {(today+timedelta(days=1)).strftime('%d/%m/%Y')}"
        items = await load_today_items()  # Tạm lấy như hôm nay (chưa crawl ngày mai)
    elif mode == "week":
        head = f"📅 Lịch trong tuần (rút gọn) từ {today.strftime('%d/%m')}"
        items = await load_today_items()  # Tạm lấy như hôm nay
    else:
        head = f"📅 Hôm nay {today.strftime('%A, %d/%m/%Y')}"
        items = await load_today_items()

    if not items:
        return "📅 Hôm nay không có tin vĩ mô quan trọng.\nChúc bạn một ngày trade thật thành công nha!"

    lines = [head]
    for it in items:
        lines.append(f"• {it.time} — {it.event} — Ảnh hưởng: {it.impact}")
    lines.append("Gợi ý: Tin mạnh → đứng ngoài 5–15’ sau khi ra tin.")
    return "\n".join(lines)
