# --- Base Python 3.11, nhẹ, ổn định cho pandas wheels ---
FROM python:3.11-slim

# Không tạo .pyc, log không buffer
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Thư mục làm việc
WORKDIR /app

# Cập nhật pip trước
RUN pip install --upgrade pip

# Cài deps
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy toàn bộ project
COPY . .

# Render sẽ cung cấp biến PORT. Uvicorn sẽ lắng nghe ở đó.
CMD ["bash", "-lc", "uvicorn cofure.app:app --host", "0.0.0.0", "--port", "${PORT}"]
