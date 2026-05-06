FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

COPY bot/requirements.txt /app/bot/requirements.txt
RUN pip install -r /app/bot/requirements.txt

COPY bot /app/bot

# Webhook listener — exposed on the compose internal network only.
EXPOSE 9000

CMD ["python", "-m", "bot.main"]
