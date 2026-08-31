FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CV_VALIDATOR_DB_PATH=/app/data/cv_validator.db \
    CV_VALIDATOR_WEIGHTS_PATH=/app/weights.yaml

COPY pyproject.toml README.md weights.yaml ./
COPY src ./src

RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

FROM base AS dev

COPY tests ./tests
COPY fixtures ./fixtures

RUN pip install --no-cache-dir ".[dev]"

CMD ["pytest", "-q"]

FROM base AS runtime

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --retries=3 --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "cv_validator.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
