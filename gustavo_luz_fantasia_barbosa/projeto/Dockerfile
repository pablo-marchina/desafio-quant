FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN python -m pip install --upgrade pip

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY apps ./apps
COPY scripts ./scripts
COPY data ./data
COPY database ./database

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "apps/api"]
