FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    BILISUMMARY_BUNDLE_DIR=/app/bilibili-summary \
    BILISUMMARY_DATA_DIR=/app/runtime \
    BILISUMMARY_ENV_FILE=/app/runtime/.env.local \
    BILISUMMARY_SUMMARY_DIR=/app/runtime/summary \
    OBSIDIAN_VAULT_PATH=/obsidian

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY bilibili-summary/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY bilibili-summary /app/bilibili-summary
COPY tools /app/tools
COPY data/config /app/data/config

WORKDIR /app/bilibili-summary
EXPOSE 18520

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "18520"]
