# One image for the whole app: Flask serves the built React UI, /api, /auth and
# Socket.IO from a single origin. See docs/DEPLOY_AZURE.md.

# ── Stage 1: build the React frontend ─────────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python runtime ──────────────────────────────────────────────────
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STATIC_DIR=/app/static \
    ENABLE_STREAM=1 \
    TRUST_PROXY=1 \
    PORT=8000

WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY --from=frontend /src/dist /app/static

RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8000

# Exactly one worker: Socket.IO rooms and the Alpaca stream live in process
# memory. Threads give concurrency (threading async mode + simple-websocket).
CMD ["sh", "-c", "exec gunicorn --worker-class gthread -w 1 --threads 50 --timeout 0 -b 0.0.0.0:${PORT} app:app"]
