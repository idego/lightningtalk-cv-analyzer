FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CV_VALIDATOR_DB_PATH=/app/data/cv_analyzer.db \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

FROM base AS dev

COPY tests ./tests
COPY scripts ./scripts

RUN pip install --no-cache-dir ".[dev]" \
    && addgroup --system app \
    && adduser --system --ingroup app app \
    && mkdir -p /app/data \
    && chown -R app:app /app/data

USER app
CMD ["pytest", "-q"]

FROM base AS geonames-init

CMD ["cv-geonames-bootstrap"]

FROM base AS runtime

RUN addgroup --system app \
    && adduser --system --ingroup app app \
    && mkdir -p /app/data \
    && chown -R app:app /app/data
USER app

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --retries=3 --start-period=5s \
    CMD python -c "import json,sys,urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8000/health')); sys.exit(0 if data.get('ready') is True else 1)"

CMD ["uvicorn", "cv_validator.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
