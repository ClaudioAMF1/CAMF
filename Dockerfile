# Imagem de produção: um único serviço servindo a API e a interface.
# (Para desenvolvimento use o docker-compose, que sobe api/db/web separados.)

# --- 1. build do frontend ---
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json ./
RUN npm install
COPY frontend/index.html frontend/vite.config.js ./
COPY frontend/src ./src
RUN npm run build

# --- 2. runtime Python ---
FROM python:3.11-slim

# Dependências de sistema do WeasyPrint (Pango/Cairo) — é por isso que este
# projeto não roda em runtime serverless.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    libffi8 shared-mime-info fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/alembic.ini .
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY --from=web /web/dist ./web

ENV FRONTEND_DIR=/app/web \
    ARMAZENAMENTO_DIR=/dados/pdfs \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# A plataforma injeta $PORT; migrations rodam antes de subir o servidor.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
