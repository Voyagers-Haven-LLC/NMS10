FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# System deps Pillow / instagrapi can need on slim. libjpeg + zlib cover
# JPEG/PNG decode for Pillow (banner handling, scraped thumbnails). curl
# is only used by the healthcheck if you want to swap to it later.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libjpeg62-turbo zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Application code
COPY backend/app /app/app
# Backup CLI + any future ops scripts
COPY backend/scripts /app/scripts

# Data lives on a named volume in compose. App writes nms10.db, backups,
# scraper logs, the bot-internal-secret, JWT secret, etc. all under /data.
RUN mkdir -p /data
ENV NMS10_DATA_DIR=/data

EXPOSE 8000

# Healthcheck mirrors the one in compose so you can also `docker run` this
# image standalone and still get health status.
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=3).read()" \
        || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
