FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/main.py .
COPY static/ ./static/

EXPOSE 6969

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "6969", "--workers", "2"]
