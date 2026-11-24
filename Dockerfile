# ---- 1. Compila el frontend (React + Vite) ----
FROM node:22-alpine AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 2. Backend FastAPI que además sirve el frontend compilado ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=America/Lima \
    STATIC_DIR=/app/static \
    ENV_FILE=/config/app.env
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=frontend /src/dist ./static

RUN useradd --system --uid 1001 app
USER app

EXPOSE 8001
# 1 solo worker: la carga programada del ERP debe correr una sola vez
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1", "--proxy-headers"]
