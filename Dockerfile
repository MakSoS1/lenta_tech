FROM node:24.10.0-bookworm-slim AS frontend
WORKDIR /build
COPY apps/ostrovok/frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY apps/ostrovok/frontend/ ./
RUN npm run build

FROM node:24.10.0-bookworm-slim AS opencode
WORKDIR /opt/opencode
COPY apps/ostrovok/opencode/package*.json ./
RUN npm ci --omit=dev --no-audit --no-fund

FROM python:3.12.14-slim-bookworm AS dependencies
RUN python -m venv /opt/venv
COPY apps/ostrovok/backend/requirements.lock /tmp/requirements.lock
RUN /opt/venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock

FROM python:3.12.14-slim-bookworm AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libstdc++6 && rm -rf /var/lib/apt/lists/* && useradd --uid 10001 --create-home traveler && mkdir /data && chown traveler:traveler /data
COPY --from=dependencies /opt/venv /opt/venv
COPY --from=opencode /usr/local/bin/node /usr/local/bin/node
COPY --from=opencode /opt/opencode /opt/opencode
WORKDIR /app
COPY apps/ostrovok/backend/app /app/apps/ostrovok/backend/app
COPY apps/ostrovok/data/reference /app/apps/ostrovok/data/reference
COPY --from=frontend /build/dist /app/apps/ostrovok/frontend/dist
ENV PATH="/opt/venv/bin:/opt/opencode/node_modules/.bin:/usr/local/bin:/usr/bin:/bin" PYTHONPATH="/app/apps/ostrovok/backend" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DB_PATH="/data/ostrovok.sqlite" LLM_MODE="opencode" OPENCODE_BIN="/opt/opencode/node_modules/.bin/opencode"
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=4s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
