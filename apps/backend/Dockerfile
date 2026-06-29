# Backend API gateway — FastAPI + uvicorn.
FROM python:3.11-slim

WORKDIR /app

# psycopg[binary] không cần build tool; cài deps trước để tận dụng layer cache.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

EXPOSE 8000

# .env nạp qua docker-compose env (ưu tiên hơn file). DB phải init trước (scripts/init_db.py).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
