# Multi-stage Dockerfile for MOD full-cycle dashboard

# --- Stage 1: Build Frontend SPA ---
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
ARG VITE_CHINA_MAP_GEOJSON_URL=
ENV VITE_CHINA_MAP_GEOJSON_URL=$VITE_CHINA_MAP_GEOJSON_URL
RUN corepack enable && corepack prepare pnpm@11.22.0 --activate
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# --- Stage 2: Production Runtime with Nginx & Python FastAPI ---
FROM python:3.12-slim AS runner
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast, reliable Python dependency installation
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /bin/uv

# Copy backend dependencies
COPY backend/pyproject.toml backend/uv.lock backend/
WORKDIR /app/backend
RUN uv sync --frozen --no-dev --no-install-project

# Copy backend source
COPY backend/app ./app
RUN uv sync --frozen --no-dev

# Copy built frontend assets
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html

# Nginx config for SPA routing and API proxy
RUN echo 'server { \
    listen 80; \
    server_name localhost; \
    location / { \
        root /usr/share/nginx/html; \
        try_files $uri $uri/ /index.html; \
    } \
    location /api/ { \
        proxy_pass http://127.0.0.1:8100; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
    } \
}' > /etc/nginx/conf.d/default.conf

WORKDIR /app
EXPOSE 80

# Start script running Nginx and FastAPI uvicorn
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1/api/health >/dev/null || exit 1

CMD ["sh", "-c", "nginx && exec /app/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8100"]
