# legado web service — Docker port
# Re-implements io.legado.app.service.WebService (HTTP :1122) +
# WebSocketServer (:1123) with a native web UI, API-compatible with legado.

FROM python:3.11-slim

# metadata
LABEL org.opencontainers.image.title="legado-web" \
      org.opencontainers.image.description="Legado book reader — Docker port (HTTP API + Web UI)" \
      org.opencontainers.image.source="https://github.com/warpdotsys/legado"

# avoid writing .pyc / buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LEGADO_WEB_PORT=1122 \
    LEGADO_DB=/data/legado.db

WORKDIR /app

# install python deps first (better layer caching)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# copy backend + frontend
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# persistent data volume (book database, cache)
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 1122 1123

HEALTHCHECK --interval=30s --timeout=5s --start-period=8s --retries=3 \
    CMD python -c "import urllib.request,sys; \
        sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:1122/',timeout=4).status==200 else 1)" \
    || exit 1

CMD ["python3", "backend/server.py"]
