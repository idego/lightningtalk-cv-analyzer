# CV Location Consistency Analyzer

Decision-support tool that checks whether a candidate's **stated location** on their CV is **consistent** with other location-bearing evidence in the same document.

> **This does not verify physical location.** A batch CV cannot prove where a person sits. Outputs are for human review only — no automated rejection or advancement.

## Scope (v1)

- **Inputs:** text-extractable PDF and DOCX, English-primary
- **Not supported:** scanned/image PDFs (no OCR), non-English CVs, live online enrichment
- **Enrichment:** offline only (`phonenumbers`, static TLD→country table)
- **Output:** JSON report with score (0–100), band (`green` / `amber` / `red` / `gray`), itemized findings, and plain-language summary

## Monorepo Layout

- `apps/api` — FastAPI backend service (current implementation)
- `apps/web` — frontend placeholder (implemented in a later issue)

## Docker (recommended)

Run the API:

```bash
docker compose up --build
```

The API is available at `http://localhost:8000`. SQLite data persists in the `cv_validator_data` volume.

Run the test suite in a container:

```bash
docker compose --profile test run --rm test
```

Optional environment variables (via shell or `.env`):

- `CV_VALIDATOR_PORT` — host port for the API (default `8000`)
- `CV_VALIDATOR_RETENTION_DAYS` — audit/report retention window (default `90`)

Example request:

```bash
curl -F "file=@apps/api/fixtures/calibration/consistent_berlin.txt;filename=cv.docx" http://localhost:8000/analyze
```

Note: use a `.docx` or `.pdf` filename for uploads; plain text fixtures are useful for library/tests but the API validates by file extension.

## Install (local backend)

```bash
cd apps/api
pip install -e ".[dev]"
```

## CLI usage (library)

```python
from pathlib import Path
from cv_validator.pipeline import analyze_cv_file, analyze_cv_text

report = analyze_cv_file(Path("cv.docx"))
print(report.band, report.score, report.summary)
```

## API

```bash
cd apps/api
uvicorn cv_validator.api.app:app --reload
```

- `POST /analyze` — single CV upload
- `POST /analyze/batch` — multiple CVs; per-file errors isolated
- `GET /health` — health check

## Calibration fixtures

Synthetic fixtures live in `apps/api/fixtures/calibration/`:

- `consistent_berlin.txt` — aligned signals
- `mismatch_us_phone.txt` — strong conflict (US phone vs claimed Germany)
- `sparse_cv.txt` — insufficient evidence → gray band

Run tests:

```bash
cd apps/api
PYTHONPATH=src pytest
```

## Weights

Signal weights and band thresholds are in `apps/api/weights.yaml`. Strong signals (phone, address) are calibrated to dominate the full weak-signal pool.

## Disclaimer

Every report is stamped: **decision-support only — not verification.** Human review is required.
