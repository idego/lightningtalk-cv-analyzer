# cv-analyzer

Local document and CV analysis pipeline.

The backend parses and validates CVs with a selected analysis strategy, runs
optional public company, education, and LinkedIn research against explicit
whitelist patterns, records detailed token usage and USD/PLN cost estimates,
and serves a Next.js web review UI.

## Architecture

- `apps/api`: FastAPI backend with a pluggable analysis strategy (`document-analysis`),
  hybrid rule/model pipeline, SQLite persistence, and public research providers.
- `apps/web`: Next.js frontend with document preview (PDF and DOCX), findings
  review, LinkedIn confirmation, contextual feedback capture, and a maintainer inbox.
- `packages/shared-types`: TypeScript contracts aligned with the API payload schema.

## Requirements

- Python 3.12+
- Node.js 22+
- `pnpm` 10+
- `uv` 0.5+
- Docker and Docker Compose (production deployment and integration verification)

## Quick start

```bash
# 1. Install dependencies
pnpm install
(cd apps/api && uv sync)

# 2. Configure environment
cp .env.example .env
# Edit .env and set at least:
# CV_VALIDATOR_ANALYSIS_STRATEGY=document-analysis
# CV_VALIDATOR_OPENAI_API_KEY=sk-...   # required if AI features enabled
# BETTER_AUTH_SECRET=...                # generate with: openssl rand -base64 32

# 3. Start development stack
make dev
```

The web app is available at `http://localhost:3001`.

## Core workflows

- **Analyze**: Upload a CV (PDF or DOCX), inspect parsed profile data, review
  findings, and browse research outcomes.
- **Recent analyses**: Reopen previously analyzed CVs with their original
  stored document preview.
- **Contextual feedback**: Submit targeted feedback on any finding, structured
  fact, or failure diagnostic.
- **Feedback inbox** (`/feedback`): Triage feedback items with status updates
  and team notes. Requires an `owner` or `reviewer` role.
- **Usage dashboard** (`/dashboard`): View lifetime token consumption, USD/PLN
  cost breakdown, and per-analysis expense details.

## Analysis strategy

The active strategy is controlled by `CV_VALIDATOR_ANALYSIS_STRATEGY`. The default
production strategy is `document-analysis`, which:

1. Converts PDF or DOCX input to clean structural text and document blocks.
2. Extracts candidate profile fields, work history, and education records.
3. Resolves locations against the local GeoNames and postal code index.
4. Identifies email patterns and flags potential anomalies.
5. Runs optional AI analysis for deep review findings and coverage gaps.
6. Surfaces high-confidence public research targets for company, education, and
   LinkedIn profiles.

## Privacy and persistence

- OpenAI requests use `store=false`.
- Never log raw CV text or raw model output.
- The API stores the validated report, not the uploaded original.
- Access tokens are hashed for ownership and are not written into audit JSON.
- Private CV fixtures and evaluation outputs belong under ignored `data/`.
- Old pilot reports are not migrated. The new default database is
  `data/cv_analyzer.db`; existing databases are never deleted implicitly.

Contextual feedback is enabled by default. It stores the signed-in author's
email, target identity, classification, short sanitized comment, the displayed
CV/report fragment being reviewed, and safe technical diagnostics. It never
stores the uploaded original, raw model output, or raw logs. Analysis data is
transient and recruiter-owned. Feedback is long-lived platform and review data
that survives analysis deletion and retention purge, similar to the AI usage
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

- Formats: PDF and DOCX.
- Maximum file size: 10 MB.
- Password-protected or encrypted files are rejected.
- Scanned documents require a readable text layer; raw image OCR is out of scope.
- Phone number matching uses libphonenumber formats.

## Testing

```bash
# Backend unit and integration tests
uv run --directory apps/api pytest tests

# Frontend tests
pnpm --dir apps/web test

# Linting and type checks
pnpm lint
(cd apps/api && uv run ruff check)
```

## Documentation

- [`docs/operations.md`](docs/operations.md): Deployment, rollback, volume
  management, and feedback access.
- [`openspec/specs/`](openspec/specs/): Detailed component specifications.
