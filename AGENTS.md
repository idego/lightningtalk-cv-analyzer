# AGENTS.md

Canonical instructions for coding agents in this repository.

## Current architecture

The API runs the `document-analysis` strategy against the shared
`base-analysis-v2` schema. Read `docs/architecture.md` before changing the
analysis pipeline. The shared layer owns validation, persistence, mechanical
primitives, UI, and research.

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
| Run the stack | `make dev` |
| Stop stack | `make dev-down` |
| Backend tests | `cd apps/api && PYTHONPATH=src .venv/bin/pytest -q` |
| Web tests | `cd apps/web && pnpm test` (Node 22) |
| Web typecheck | `cd apps/web && pnpm typecheck` |
| Web build | `cd apps/web && pnpm build` |

API endpoints include `GET /health`, `GET /operations/{metrics,status}`,
`POST /analyze`, `POST /analyze/batch`, analysis lifecycle endpoints,
settings/retention, per-analysis feedback, the `/internal/feedback` inbox
(authorized only by the web proxy), and company/education/LinkedIn research.
The browser reaches the API only through Next.js routes under
`apps/web/src/app/api/`.

## Code conventions

- Core backend logic lives in `apps/api/src/cv_validator/`; FastAPI remains a
  thin boundary in `cv_validator/api/`.
- Preserve auth, upload/batch limits, preview, ownership, retention, deletion,
  recent analyses, GeoNames, and research unless the owner changes scope.
- Match existing style and keep diffs focused.
- Use environment variables for runtime configuration.
- Use Conventional Commits (`<type>[scope]: <description>`).
- Every capability lives in an `openspec/specs/<capability>/spec.md`; ship a
  new feature through `/opsx:propose` → apply → archive, or update the spec in
  the same change when adjusting behavior.
- Create commits only when explicitly asked.
- Never push unless explicitly asked.
- If elevated access is needed, use graphical Polkit rather than `sudo`.

## OpenSpec

Keep source-of-truth specs aligned when archiving completed changes. Do not
restore archived contracts for removed analysis systems.
