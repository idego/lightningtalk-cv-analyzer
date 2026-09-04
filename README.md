# CV Analyzer

CV Analyzer analyzes CVs with Docling document conversion and pinned OpenAI
model passes, producing reports in the `base-analysis-v2` contract.

The previous deterministic Document Understanding, Structural Audit, ESCO,
national-ID redaction, score/band, file metadata, and live-link checker have
been removed. They are not compatibility surfaces.

## Architecture

```text
PDF or DOCX upload
    -> Docling 2.124.0 native-text conversion (OCR disabled)
    -> thin SourceDocument evidence projection
    -> concurrent profile, employment, and education model specialists
    -> field and relation validation plus mechanical candidates
    -> sequential model reviewer with validated ID-based operations
    -> base-analysis-v2 validation
    -> persistence and UI
    -> automatic company, education, and LinkedIn research
```

Every semantic value needs literal source evidence. A reviewer may add a missing candidate
only when the same evidence and relation validation accepts it.

The specialists use pinned `gpt-5.6-luna` with reasoning effort `none`; the
reviewer uses `low`; public research calls use `medium`. Responses API storage is disabled and base analysis uses
no tools. Without AI credentials the strategy still converts documents and
returns an explicit unavailable/partial result instead of another parser.

Mechanical code is limited to phones, e-mails, literal URLs, postal-pattern
candidates, e-mail provider typos, geographic resolution, and informational EU
status. A postal-looking token is not accepted as the candidate's address
without supported context.

See the current [architecture](docs/architecture.md) for durable boundaries and
the authoritative executable contracts.

## Development

```bash
make dev
make dev-down
cd apps/api && PYTHONPATH=src .venv/bin/pytest -q
cd apps/web && pnpm test        # requires Node 22 (type stripping)
cd apps/web && pnpm typecheck
cd apps/web && pnpm build
```

`make dev` also publishes the API on `http://127.0.0.1:8001/docs` (Swagger)
through `docker-compose.dev.yml`; `make deploy` never does.

The web app is available at `http://127.0.0.1:3001/analyze`. Compose uses
project `cv-analyzer`, API database `/app/data/cv_analyzer.db`, and auth
database `/app/data/auth.db`. A stack created under the former project name
`cv-analyzer-document-analysis` keeps its volumes under that name; to reuse its
data, start with `COMPOSE_PROJECT_NAME=cv-analyzer-document-analysis` and pin
`CV_VALIDATOR_DB_PATH` and `BETTER_AUTH_DB_PATH` to the old `docling_luna*.db`
paths in the env file, or copy the volumes once while the stack is stopped.

On the first `make dev` or `make deploy`, the one-shot `geonames-init` service
downloads the configured official GeoNames sources and builds both locality and
postal indexes in the project-scoped `geonames_data` volume. The API waits for
that job and mounts its completed `current` release read-only. Later starts
validate and reuse the volume without downloading. The checked-in `config/geonames.lock` pins the accepted `GEONAMES_SNAPSHOT_VERSION`; refresh the lock and version together when intentionally updating upstream data; allow at least 3 GiB of free space
for archives, staging files, and indexes.

For a host with no outbound access, prepare an approved directory containing
both index/manifest pairs and run `REFERENCE_DATA_MODE=operator make deploy` with
`CV_VALIDATOR_REFERENCE_DATA_DIR` set in `.env`. See
[`docs/reference-data/geonames.md`](docs/reference-data/geonames.md) for recovery,
refresh, and rollback details.

`GET /health` reports `ready: false` when the analysis model client is not
configured; uploads then fail with `analysis_strategy_unavailable` and are not
persisted as successful reports. Each attempted analysis has owner-scoped,
PII-safe diagnostics and an immutable AI token/cost ledger at
`GET /analyses/{analysis_id}/diagnostics`. Rates are versioned in code and can
be overridden with `CV_VALIDATOR_PRICING_PATH`; unknown model pricing leaves
the cost null without discarding token usage. Reusable research cache hits
record zero current-call tokens and separate saved usage/cost provenance.

## Deployment

Production is Compose-based. Copy and fill `.env`, keep `WEB_HOST=127.0.0.1`, run `make deploy-check`, then `make deploy`. The public subdomain terminates TLS at an external reverse proxy and forwards only to the loopback-bound web port; the API remains private on the Compose network. Full environment, backup, rollback, feedback-access, retention, and reverse-proxy notes live in [`docs/operations.md`](docs/operations.md).

## Privacy and persistence

- OpenAI requests use `store=false`.
- Never log raw CV text or raw model output.
- The API stores the validated report and, after report commit, the original PDF/DOCX only for owner-scoped preview within the same retention window.
- Analysis ownership uses the authenticated Better Auth user id server-side; no owner capability token is returned to the browser or written into report/audit JSON.
- Private CV fixtures and evaluation outputs belong under ignored `data/`.
- Old pilot reports are not migrated. The new default database is
  `data/cv_analyzer.db`; existing databases are never deleted implicitly.

Contextual feedback is enabled by default. It stores the signed-in author's
email, target identity, classification, short sanitized comment, the displayed
CV/report fragment being reviewed, and safe technical diagnostics. It never
stores the uploaded original, raw model output, or raw logs. Analysis data is
transient and recruiter-owned, while feedback is long-lived platform/review
data that survives analysis deletion and retention purge, like the AI usage
ledger. Setup and access management are documented in
[`docs/operations.md`](docs/operations.md).

## Public research

Company, education, and LinkedIn research remains optional. Subjects come only
from accepted, evidence-supported base-analysis records. Reusable cache entries
are keyed per public subject, support partial hits, and carry hit/miss
provenance, original research timestamps, refresh, and cache audit entries.

Research confidence is intentionally conservative: high confidence requires
multiple consistent public signals, and LinkedIn discovery requires both name
support and compatible experience or education context. Results remain possible
matches, never identity verification. The LinkedIn Profiles header also provides
one user-initiated people-search shortcut; it does not replace or trigger LinkedIn
Research and no per-profile search shortcuts are shown. Each company and
education entry in the CV overview, and each completed company or education
research result, carries a compact Google Search shortcut built only from the
visible public subject; self-employment entries get none.

## Supported documents and limitations

Only text-bearing PDF and DOCX files are supported. Image-only or scan-only
documents fail with `document_text_layer_unavailable`; OCR is never attempted.
The minimal Docling runtime installs only PDF/DOCX conversion extras and sets
offline flags, so it has no model assets to download at runtime. Results are
recruiter decision support and never verify a candidate or their location.
