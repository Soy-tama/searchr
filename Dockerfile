FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/main.py .
COPY static/ ./static/

EXPOSE 4444

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "4444", "--workers", "2"]
