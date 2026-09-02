# CV Analyzer

This branch implements the Docling plus GPT-5.6 Luna analysis variant against
the shared `base-analysis-v2` contract.

The previous deterministic Document Understanding, Structural Audit, ESCO,
national-ID redaction, score/band, file metadata, and live-link checker have
been removed. They are not compatibility surfaces.

## Architecture

```text
PDF or DOCX upload
    -> Docling 2.124.0 native-text conversion (OCR disabled)
    -> thin SourceDocument evidence projection
    -> concurrent profile, employment, and education Luna specialists
    -> field and relation validation plus mechanical candidates
    -> sequential Luna reviewer with validated ID-based operations
    -> base-analysis-v2 validation
    -> persistence and UI
    -> automatic company, education, and LinkedIn research
```

Every semantic value needs literal source evidence. A reviewer may add a missing candidate
only when the same evidence and relation validation accepts it.

The specialists use pinned `gpt-5.6-luna` with reasoning effort `none`; the
reviewer uses `low`. Responses API storage is disabled and base analysis uses
no tools. Without AI credentials the strategy still converts documents and
returns an explicit unavailable/partial result instead of another parser.

Mechanical code is limited to phones, e-mails, literal URLs, postal-pattern
candidates, e-mail provider typos, geographic resolution, and informational EU
status. A postal-looking token is not accepted as the candidate's address
without supported context.

See:

- [shared reset handoff](docs/cv-analyzer-architecture-reset-handoff.md)
- [Docling plus Luna handoff](docs/handoffs/docling-luna.md)
- [Luna-only handoff](docs/handoffs/luna-only.md)

## Development

```bash
make dev
make dev-down
cd apps/api && PYTHONPATH=src .venv/bin/pytest -q
cd apps/web && npm test
cd apps/web && npm run typecheck
cd apps/web && npm run build
```

The isolated web app is available at `http://127.0.0.1:3021/analyze`. Compose
uses project `cv-analyzer-docling-luna`, API database
`/app/data/docling_luna.db`, and auth database
`/app/data/docling_luna_auth.db`.

## Privacy and persistence

- OpenAI requests use `store=false`.
- Never log raw CV text or raw model output.
- The API stores the validated report, not the uploaded original.
- Access tokens are hashed for ownership and are not written into audit JSON.
- Private CV fixtures and evaluation outputs belong under ignored `data/`.
- Old pilot reports are not migrated. The new default database is
  `data/docling_luna.db`; existing databases are never deleted implicitly.

Contextual feedback is disabled by default. When enabled, it stores opaque
target identities, closed classifications, short sanitized comments and safe
technical diagnostics; it never stores CV/report content or raw logs. Feedback
is removed with its parent analysis. Setup and staged enablement are documented
in [`docs/operations.md`](docs/operations.md).

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
Research and no per-profile search shortcuts are shown.

## Supported documents and limitations

Only text-bearing PDF and DOCX files are supported. Image-only or scan-only
documents fail with `document_text_layer_unavailable`; OCR is never attempted.
The minimal Docling runtime installs only PDF/DOCX conversion extras and sets
offline flags, so it has no model assets to download at runtime. Results are
recruiter decision support and never verify a candidate or their location.
