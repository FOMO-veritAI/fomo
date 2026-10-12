# syntax=docker/dockerfile:1
# Imagens do FOMO (o deploy completo, com a VeritAI, fica em deploy/):
#   docker build --target api -t fomo-api:local .     # API FastAPI na porta 8000, modo serviço, sem torch
#   docker build --target web -t fomo-web:local .     # Caddy: frontend em / e proxy da API em /api, com HTTPS
#   docker build --target teste .                     # suíte do backend com Python 3.12 (não vira imagem final)

ARG PYTHON_IMAGE=python:3.12-slim
ARG NODE_IMAGE=node:24-slim
ARG CADDY_IMAGE=caddy:2

# --- Dependências da API em um venv isolado ---------------------------------------------------------
FROM ${PYTHON_IMAGE} AS dependencias
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/opt/venv/bin:$PATH
RUN python -m venv /opt/venv
COPY backend/requirements.txt /tmp/requirements.txt
# Só o modo serviço: o pipeline embutido (torch) fica em requirements-embutido.txt, fora da imagem.
RUN pip install -r /tmp/requirements.txt \
 && ! pip list 2>/dev/null | grep -iE '^(torch|transformers|sentence-transformers) '

# --- Testes com Python 3.12 (só com --target teste) -------------------------------------------------
FROM dependencias AS teste
WORKDIR /app
COPY backend/app ./backend/app
COPY backend/tests ./backend/tests
RUN python -m unittest discover -s backend/tests

# --- API ----------------------------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS api
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp \
    VERITAI_MODO=servico
# Mesmo padrão da VeritAI: uid/gid 10001, que só escreve no volume de dados (banco e anexos) e em /tmp.
RUN groupadd --system --gid 10001 fomo \
 && useradd --system --no-create-home --uid 10001 --gid 10001 --home-dir /tmp --shell /usr/sbin/nologin fomo \
 && mkdir -p /app/backend/data \
 && chown fomo:fomo /app/backend/data
COPY --from=dependencias /opt/venv /opt/venv
WORKDIR /app
COPY backend/app ./backend/app
USER fomo
EXPOSE 8000
VOLUME ["/app/backend/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"]
# Um processo só: a análise roda em segundo plano dentro dele, e o SQLite não aceita várias réplicas.
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- Frontend -----------------------------------------------------------------------------------------
FROM ${NODE_IMAGE} AS frontend
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY angular.json tsconfig.json tsconfig.app.json ./
COPY public ./public
COPY src ./src
# Mesma origem por padrão: o Caddy serve o frontend e repassa /api para a API, sem CORS.
ARG FOMO_API_URL=/api
RUN npx ng build --define "FOMO_API_URL=$(node -p 'JSON.stringify(process.env.FOMO_API_URL)')"

# --- Web: Caddy com HTTPS automático ------------------------------------------------------------------
FROM ${CADDY_IMAGE} AS web
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend /src/dist /srv/fomo
