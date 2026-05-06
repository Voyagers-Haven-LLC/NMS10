FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

COPY bot/requirements.txt /app/bot/requirements.txt
RUN pip install -r /app/bot/requirements.txt

COPY bot /app/bot

# The bot reads the rate-limit-bypass secret from <NMS10_DATA_DIR>/.bot-internal-secret.
# In compose we mount the backend's named volume into the bot at /data so
# both processes see the same value the backend auto-generates on first boot.
ENV NMS10_DATA_DIR=/data

# Webhook listener — exposed on the compose internal network only.
EXPOSE 9000

CMD ["python", "-m", "bot.main"]
