# CV Location Consistency Analyzer

Decision-support tool that checks whether a candidate's **stated location** on their CV is **consistent** with other location-bearing evidence in the same document.

> **This does not verify physical location.** A batch CV cannot prove where a person sits. Outputs are for human review only — no automated rejection or advancement.

## Scope (v1)

- **Inputs:** text-extractable PDF and DOCX, English-primary
- **Not supported:** scanned/image PDFs (no OCR), non-English CVs, live online enrichment
- **Enrichment:** offline only (`phonenumbers`, static TLD→country table)
- **Output:** JSON report with legacy-compatible score/band fields, itemized findings, file details, declared-link inspection outcomes, and a plain-language summary
- **File details:** bounded PDF/DOCX standard metadata shown as reviewer context only; metadata never proves authenticity or location
- **Declared links:** visible HTTP(S) URLs and embedded PDF/DOCX hyperlinks are deduplicated, provenance-aware, and optionally checked against a safe public-link policy

## Monorepo Layout

- `apps/api` — FastAPI backend service (current implementation)
- `apps/web` — Next.js frontend (Google auth, upload panel, analysis results)

## Docker (recommended)

Create the ignored local environment file, enable AI, provide the OpenAI key,
and point it at the approved GeoNames directory:

```bash
cp .env.example .env.local
# edit .env.local; never commit it
make dev
```

`make dev` is the canonical full-stack development command. It validates the
environment and pinned GeoNames checksums, builds the services, waits for every
required capability, and then verifies the public health endpoint.

```bash
make dev
```

The local dev stack is available at `http://localhost:3001` and binds only to
`127.0.0.1`. This command enables an authentication bypass that only works with
a loopback `BASE_URL`; regular `docker compose up --build` continues to require
configured Google OAuth.

Stop the local stack with `make dev-down`.

The web app is available at `http://127.0.0.1:3001`. A plain Compose invocation
retains safe defaults and is not the supported full-development path.

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
- `CV_VALIDATOR_SMALL_LOCALITY_MAX_POPULATION` — informational review threshold for resolved non-EU localities (default `10000`; set `0` to disable; never changes score)
- `CV_VALIDATOR_AI_ENABLED` — makes Document AI and company, education, and LinkedIn research available; defaults to `false`
- `CV_VALIDATOR_AI_TRANSPORT_RETRY_LIMIT` — retryable timeout/network/429/5xx retries per AI analysis (default `1`)
- `CV_VALIDATOR_AI_INVALID_RESPONSE_RETRY_LIMIT` — fresh retries after invalid model output (default `1`)
- `CV_VALIDATOR_AI_ABSOLUTE_ATTEMPT_LIMIT` — absolute attempts including the initial AI call (default `3`)
- `OPENAI_API_KEY` — required only when `CV_VALIDATOR_AI_ENABLED=true`; keep it outside Git
- `CV_VALIDATOR_BATCH_MAX_FILES` — maximum files accepted by one sequential batch request (default `4`)
- `CV_VALIDATOR_BATCH_MAX_BYTES` — maximum combined readable upload bytes in one batch (default `20971520`, 20 MiB)
- `CV_VALIDATOR_LINK_CHECK_ENABLED` — enables bounded public HTTP(S) link checks (default `true`; set `false` for offline/degraded operation)
- `CV_VALIDATOR_LINK_CHECK_PROTOCOLS` — comma-separated allowed protocols, limited to `http,https` (default `https,http`)
- `CV_VALIDATOR_LINK_CHECK_PORTS` — comma-separated allowlisted TCP ports (default `80,443`)
- `CV_VALIDATOR_LINK_CHECK_TIMEOUT_SECONDS` — per-request timeout (default `5`)
- `CV_VALIDATOR_LINK_CHECK_MAX_RESPONSE_BYTES` — maximum streamed GET response bytes (default `65536`)
- `CV_VALIDATOR_LINK_CHECK_MAX_REDIRECTS` — maximum manually validated redirects (default `3`)
- `CV_VALIDATOR_LINK_CHECK_MAX_CONCURRENCY` — maximum concurrent link checks per file (default `4`)
- `CV_VALIDATOR_LINK_CHECK_MAX_RETRIES` — bounded retry count for transient network failures (default `0`)
- `CV_VALIDATOR_LINK_CHECK_TOTAL_BUDGET_SECONDS` — total link-check budget per file (default `20`)
- `CV_VALIDATOR_LINK_CHECK_USER_AGENT` — fixed non-candidate-specific checker user agent
- `CV_VALIDATOR_LINKEDIN_CONNECTION_THRESHOLD` — public, cited count-completeness threshold (default `500`; unknown counts are never negative evidence)
- `CV_VALIDATOR_LINKEDIN_MAX_PROFILES` — maximum number of sourced, plausible name-matched profiles retained by one discovery run (default `3`, maximum `20`)
- `CV_VALIDATOR_RESEARCH_CACHE_TTL_DAYS` — reusable public research-fact cache TTL (development default `30`)

Retention is runtime-configurable and applies to the complete candidate-analysis
graph. Production cost limits are intentionally not approved yet. See
[`docs/operations.md`](docs/operations.md).

The Slice 3 AI foundation pins `gpt-5.6-luna` with medium reasoning, a 120-second
request timeout, zero provider-SDK retries, `store=false`, no tools, and a 4,096
output-token ceiling. The feature is disabled by default. Enabling it without
`OPENAI_API_KEY` fails during application startup. When enabled, each CV uses
an independent synchronous Responses API request. A refused, timed-out, or
invalid AI response fails closed and leaves the deterministic report available.
Application-owned retries default to one retryable transport retry, one invalid
response retry, and three attempts in total. Other 4xx responses are not
retried. A failed result can be retried manually while its redacted, process-local
retry context remains available; this does not repeat upload or research.
The API stores the validated AI result, model and contract versions, token
usage, and audit payload under one stable analysis ID. AI findings are review
notes and never change the deterministic score, band, facts, or rule findings.
The Settings master AI switch opts a user out of Document AI and every manual
or automatic research feature without restarting the stack. Deterministic
analysis remains available. The server environment remains authoritative: the
browser cannot enable AI on a deployment where it is unavailable.

The tracked Document Analyzer prompt and strict output schema live in
`apps/api/src/cv_validator/ai/contracts/`. Runtime request construction and the
private eval harness read those same bundled files. The current base-report
contract uses a date-versioned prompt and a strict response schema: the model
cites line IDs and code materializes excerpts, owns bookkeeping, and may yield a
partial result with a neutral validation warning while preserving supported
output.

GeoNames runtime data is optional and is never baked into the image. See
[`docs/reference-data/geonames.md`](docs/reference-data/geonames.md) for the
approved-pair layout and explicit Compose overlay command.

For production, start from the root `.env.example` using an ignored `.env`:

```bash
cp .env.example .env
make deploy-check
# after checking out the exact reviewed commit:
make deploy
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
- `POST /analyses/{analysis_id}/research/company` — bounded, synchronous company research for a stored analysis
- `GET /health` — health check

Completed reports may contain two optional sections:

- `file_details` contains only the allowlisted PDF/DOCX fields and their
  availability/extractor versions. It is neutral document context and never
  contributes to score or band.
- `link_inspection` contains deduplicated visible/embedded link outcomes. A
  `SUSPICIOUS` result is a concrete document-review prompt for a mismatch,
  lookalike, unsafe destination, unrelated redirect, or not-found CV claim.
  `UNAVAILABLE` means the check was inconclusive, for example because of DNS,
  timeout, rate limiting, anti-bot behavior, or access control. Neither state
  is a candidate-level verdict or an automated hiring action.

Link checking is deliberately bounded and privacy-preserving: only public
HTTP(S) destinations are eligible; credentials, non-allowlisted ports, private
or metadata addresses, unsafe redirects, cookies, and candidate credentials
are rejected. Redirects are followed manually with per-hop DNS/IP validation,
automatic redirects disabled, a fixed user agent, and discarded response
bodies. Persistence stores only sanitized report fields, not response bodies,
request headers, cookies, or URL query/fragment material. The checker does not
use AI or a paid service. Link outcomes can be false-positive attention prompts
and require human review.

The V1 batch endpoint remains deliberately sequential. Its default cap is four
files and 20 MiB of readable upload data, checked before any CV analysis starts.
The four-file cap is based on the existing four-CV Luna measurement: about
97.5 seconds total (about 24.4 seconds per CV on average). It is a conservative
synchronous limit, not a throughput guarantee: the configured per-model-call
timeout is still 120 seconds, so production concurrency and larger batches must
be measured separately before raising it. Both limits are configurable through
the environment and do not introduce a background queue.

The frontend retains score and band in API/history compatibility types, but the
recruiter-facing report does not present them as the overall CV or candidate
assessment. It leads with concrete findings, structured facts, file details,
link outcomes, and the decision-support disclaimer.

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

All consumers use canonical `RawDocument.pages`, `RedactedDocument.pages`, or
their `source_lines`. The former Slice 1 document-level `lines`,
`contact_region`, and `body_region` compatibility views have been removed.
`SourcePage.lines` remains the canonical page-local line/offset mapping.

The ingestion threshold is evaluated once for the whole document. A meaningful
token has at least two characters after surrounding Unicode punctuation is
removed and contains at least one Unicode letter. Zero meaningful tokens return
the empty or scan-only extraction error; a positive count below the configured
threshold returns the distinct insufficient-text error.

## Weights

Signal weights and band thresholds are in `apps/api/weights.yaml`. Slice 2B
does not modify this approved file. Only the aggregate person-owned phone
comparison is active; the remaining prototype keys are dormant legacy
configuration and are not read by the deterministic scorer.

Slice 2B deliberately preserves the configured minimum of two independent
deterministic evidence categories. The current deterministic core has only one
scoreable category (aggregate person-owned phone country), so reports remain
gray until separate anonymous calibration and project-owner approval add
enough defensible evidence. Gray means insufficient independent deterministic
evidence; it is not a problem flag, negative result, or hiring recommendation.
Legacy weight keys that are no longer scoring inputs remain dormant so this
slice does not silently change the approved configuration.

When fewer than two independent categories are available, the compatible
numeric API field remains at the neutral configured base score even if the
itemized phone finding supports or conflicts. The UI shows that the report was
not assessed instead of presenting that number as a verdict. A missing unique
claim remains 0/gray.

## EU informational observations

Outside-EU observations use the ISO-2 membership set `eu27-2026-08-21`, based
on the official [EU countries list](https://european-union.europa.eu/principles-countries-history/eu-countries_en).
The set is EU-27, not EEA, Switzerland, or the United Kingdom. Phone and stated
location are separate informational categories. A combined observation needs
both categories and both must be non-EU; mixed EU/non-EU evidence is reported
separately. V1 has no calibrated locality-size rule, so a resolved non-EU
locality is explicitly `small_locality_not_evaluated` rather than classified.
None of these observations establishes nationality, identity, physical
presence, work eligibility, or fraud, and all have zero score impact.

## Disclaimer

Every report is stamped: **decision-support only — not verification.** Human review is required.
Company research remains opt-in per stored analysis. `POST
/analyses/{analysis_id}/research/company` uses the Responses API `web_search`
tool with at most four searches, a 120-second request timeout, no automatic
retry, and `store=false`. Reusable research sends only validated public
organization subjects—not CV dates, locations, relations, evidence, raw CV
text, or candidate contact data. Completed results are idempotent for the research contract version and
persist citations, searches, access time, uncertainty, versions, and usage in
SQLite; they never change deterministic score or band.
