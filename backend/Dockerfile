FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# mock 運用（鍵なし）なら false のままで軽いイメージになる。
# 実 API / Firestore / GCS を使うときは --build-arg WITH_LIVE_DEPS=true。
ARG WITH_LIVE_DEPS=false

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libjpeg62-turbo zlib1g \
    && rm -rf /var/lib/apt/lists/*

# live 側は依存が多く、pip に解かせると数十分かかる。解決済みの requirements-lock.txt を使う。
COPY requirements.txt requirements-lock.txt ./
RUN if [ "$WITH_LIVE_DEPS" = "true" ]; then \
      pip install --no-cache-dir --no-deps -r requirements-lock.txt; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi

COPY . .

RUN mkdir -p /data/storage

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
