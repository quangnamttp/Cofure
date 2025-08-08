# Python 3.11 ổn định cho pandas (wheel có sẵn)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Cập nhật pip và cài deps
RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy toàn bộ project vào container
COPY . .

# Render truyền biến PORT vào container → dùng ${PORT}
CMD ["bash", "-lc", "uvicorn cofure.app:app --host 0.0.0.0 --port ${PORT}"]
