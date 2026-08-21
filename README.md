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
- `apps/web` — Next.js frontend (Google auth, upload panel, analysis results)

## Docker (recommended)

For local development without external sign-in, run:

```bash
make dev
```

The local dev stack is available at `http://localhost:3001` and binds only to
`127.0.0.1`. This command enables an authentication bypass that only works with
a loopback `BASE_URL`; regular `docker compose up --build` continues to require
configured Google OAuth.

Stop the local stack with `make dev-down`.

Run the full stack (web + private api):

```bash
docker compose up --build
```

The web app is available at `http://localhost:3000` by default. Set `WEB_PORT=3001` in `.env` to publish on port 3001 instead (container always listens on `3000`).

- `web` is the only host-exposed service.
- `api` is reachable only on the internal compose network (`http://api:8000`).
- SQLite data persists in named volumes: `web_auth_data` (auth) and `cv_validator_data` (backend audit DB).

Run the test suite in a container:

```bash
docker compose --profile test run --rm test
```

Optional environment variables (via shell or `.env`):

- `WEB_PORT` — host port for the web app (default `3000`; set to `3001` in `.env` when needed)
- `BASE_URL` / `BETTER_AUTH_URL` — external URL used by web auth callbacks
- `BETTER_AUTH_SECRET` — random 32+ char secret for Better Auth
- `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` — Google OAuth credentials
- `ALLOWED_EMAIL_DOMAINS` — comma-separated allowed domains (default `idego.io`)
- `CV_VALIDATOR_RETENTION_DAYS` — audit/report retention window (default `90`)
- `CV_VALIDATOR_MINIMUM_MEANINGFUL_TOKENS` — minimum document-level meaningful-token count (default `5`)

Start from the root `.env.example`:

```bash
cp .env.example .env
```

## Deployment note (subdomain + TLS)

Deploy this stack behind your host reverse proxy (nginx/Caddy/Cloudflare Tunnel):

- terminate TLS at the host proxy for your `<name>.idego.*` subdomain,
- forward public traffic to `web` only,
- keep `api` unexposed from the host network.

This project is intended for container-hosted deployment, not Vercel.

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

## Ingestion model

Ingestion keeps canonical per-page source text with stable positional page IDs
(`page-0001`, `page-0002`, ...), ordered source lines, and page-local character
offsets. PDF pages retain their real boundaries. DOCX files are split only at
explicit hard page breaks or `pageBreakBefore`; rendered pagination markers are
ignored and a document without explicit breaks is one logical page.

`ParsedCV.lines`, `contact_region`, and `body_region` are compatibility-only
views for the Slice 1 deterministic report. They are derived from canonical
pages and must not be used by new code.

The ingestion threshold is evaluated once for the whole document. A meaningful
token has at least two characters after surrounding Unicode punctuation is
removed and contains at least one Unicode letter. Zero meaningful tokens return
the empty or scan-only extraction error; a positive count below the configured
threshold returns the distinct insufficient-text error.

## Weights

Signal weights and band thresholds are in `apps/api/weights.yaml`. Strong signals (phone, address) are calibrated to dominate the full weak-signal pool.

## Disclaimer

Every report is stamped: **decision-support only — not verification.** Human review is required.
