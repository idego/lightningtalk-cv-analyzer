FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CV_VALIDATOR_DB_PATH=/app/data/cv_analyzer_v2.db

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

FROM base AS dev

COPY tests ./tests
COPY fixtures ./fixtures
COPY scripts ./scripts
COPY reference_data ./reference_data

RUN pip install --no-cache-dir ".[dev]"

CMD ["pytest", "-q"]

FROM base AS runtime

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --retries=3 --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "cv_validator.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
