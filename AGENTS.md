# AGENTS.md

Canonical instructions for coding agents in this repository.

## Current architecture

This branch is the clean shared base for two document-analysis experiments.
Read `docs/cv-analyzer-architecture-reset-handoff.md` before changing the
analysis pipeline. Variant-specific work uses:

- `docs/handoffs/docling-luna.md`;
- `docs/handoffs/luna-only.md`.

The shared branch owns the `AnalysisStrategy` port, `base-analysis-v2`
schema, persistence, mechanical primitives, UI, and research. It intentionally
has no concrete analysis strategy.

Do not reintroduce the removed deterministic Document Understanding,
Structural Audit, ESCO, national-ID redaction, score/band/weights, file
metadata, live link inspection, or the old monolithic document-AI retry path.
Old pilot reports are not a compatibility requirement.

## Product boundaries

- The system is recruiter decision support, never automatic hiring judgment.
- Do not claim to verify identity, honesty, residence, physical location,
  nationality, or work eligibility.
- Semantic profile, employment, and education values require literal evidence.
- Record relations require evidence that their fields belong together.
- A reviewer may add a missing candidate only when the normal evidence and
  relation validation accepts it.
- A postal-looking token remains a candidate until supported address context
  accepts it.
- Public research receives only accepted evidence-supported subjects.
- Never log or commit private CV content, excerpts, model output, or secrets.
- OpenAI response storage remains disabled.

## Commands

| Task | Command |
| --- | --- |
| Run shared base | `make dev ALLOW_DEGRADED=true` |
| Run a strategy variant | `make dev` |
| Stop stack | `make dev-down` |
| Backend tests | `cd apps/api && PYTHONPATH=src .venv/bin/pytest -q` |
| Web tests | `cd apps/web && npm test` |
| Web typecheck | `cd apps/web && npm run typecheck` |
| Web build | `cd apps/web && npm run build` |

API endpoints include `GET /health`, `POST /analyze`,
`POST /analyze/batch`, analysis lifecycle endpoints, settings/retention, and
company/education/LinkedIn research.

## Code conventions

- Core backend logic lives in `apps/api/src/cv_validator/`; FastAPI remains a
  thin boundary in `cv_validator/api/`.
- Preserve auth, upload/batch limits, preview, ownership, retention, deletion,
  recent analyses, GeoNames, and research unless the owner changes scope.
- Match existing style and keep diffs focused.
- Use environment variables for runtime configuration.
- Use Conventional Commits.
- Create commits only when explicitly asked.
- Never push unless explicitly asked.
- If elevated access is needed, use graphical Polkit rather than `sudo`.

## Branching

Do not use a `codex/` prefix. The planned experiment branches are:

- `experiment/docling-luna-analysis`;
- `experiment/luna-only-analysis`.

They must start from the exact same authorized shared-base commit and run in
separate worktrees with separate Compose project names, ports, databases,
volumes, and local env files.

## OpenSpec

The reset itself is not an OpenSpec change. Do not create one for it. Preserve
unrelated active proposals and the owner's untracked contextual-feedback
prototype files.
