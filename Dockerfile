# Python 3.11 ổn định (có wheel cho pandas)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Cập nhật pip trước
RUN pip install --upgrade pip

# Cài dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy toàn bộ project
COPY . .

# Chạy uvicorn dùng asyncio loop (hợp với app.py đã sửa)
CMD ["bash", "-lc", "uvicorn cofure.app:app --host 0.0.0.0 --port ${PORT} --loop asyncio"]
