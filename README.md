# CV Analyzer

CV Analyzer is being reset around one shared report contract and two isolated
document-analysis experiments:

- Docling plus GPT-5.6 Luna;
- GPT-5.6 Luna with the original file input.

The shared branch intentionally contains no installed analysis strategy.
`POST /analyze` returns `analysis_strategy_unavailable` until one variant
provides an `AnalysisStrategy`.

The previous deterministic Document Understanding, Structural Audit, ESCO,
national-ID redaction, score/band, file metadata, and live-link checker have
been removed. They are not compatibility surfaces.

## Shared architecture

```text
PDF or DOCX upload
    -> AnalysisInput
    -> variant AnalysisStrategy
    -> base-analysis-v2 validation
    -> persistence and UI
    -> optional company, education, and LinkedIn research
```

Both variants must return the same profile, employment, education, reviewer,
mechanical, provenance, status, version, and usage contract. Every semantic
value needs literal source evidence. A reviewer may add a missing candidate
only when the same evidence and relation validation accepts it.

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
make dev ALLOW_DEGRADED=true  # shared base only
make dev-down
cd apps/api && PYTHONPATH=src .venv/bin/pytest -q
cd apps/web && npm test
cd apps/web && npm run typecheck
cd apps/web && npm run build
```

The web app is available at `http://127.0.0.1:3001/analyze` after the dev stack
starts. On the shared branch health is intentionally degraded because no
analysis strategy is installed, so the explicit `ALLOW_DEGRADED=true` is
required. Variant branches should use plain `make dev` and must become ready.

## Privacy and persistence

- OpenAI requests use `store=false`.
- Never log raw CV text or raw model output.
- The API stores the validated report, not the uploaded original.
- Access tokens are hashed for ownership and are not written into audit JSON.
- Private CV fixtures and evaluation outputs belong under ignored `data/`.
- Old pilot reports are not migrated. The new default database is
  `data/cv_analyzer_v2.db`; existing databases are never deleted implicitly.

## Public research

Company, education, and LinkedIn research remains optional. Subjects come only
from accepted, evidence-supported base-analysis records. Reusable cache results
carry hit/miss provenance and analysis-owned cache audit entries.
