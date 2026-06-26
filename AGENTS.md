# AGENTS.md

Canonical instructions for AI coding agents working in this repo
(Cursor, Claude Code, Codex, etc.). Tool-specific files (`CLAUDE.md`,
`.cursor/rules/*.mdc`) defer to this document for shared rules and only
add tool-specific notes.

---

## 1. Project at a glance

- **Product:** CV Location Consistency Analyzer — decision-support tool
  for recruiters reviewing candidate CVs.
- **What it does:** Compares a candidate's **stated location** (from the
  CV header/contact block) against independent circumstantial evidence in
  the same document (phone country code, postal format, employer location,
  date conventions, etc.).
- **What it does NOT do:** Verify physical location. A batch CV cannot
  prove where a person sits. Never auto-reject or auto-advance candidates.
- **Stack:** Python 3.11+, FastAPI, pdfplumber, python-docx, phonenumbers,
  SQLite (audit/persistence), Docker Compose.
- **Monorepo layout:** `apps/api` (backend), `apps/web` (frontend placeholder).
- **Package:** `apps/api/src/cv_validator/` — library-first, FastAPI wrapper.

See `README.md` for usage. Specs and active work live under `openspec/`.

---

## 2. Commands you can run

| Task | Command |
| --- | --- |
| Run API (Docker) | `docker compose up --build` |
| Run tests (Docker) | `docker compose --profile test run --rm test` |
| Run tests (local) | `cd apps/api && PYTHONPATH=src pytest` |
| Run API (local) | `cd apps/api && uvicorn cv_validator.api.app:app --reload` |
| OpenSpec status | `openspec status --change "<name>"` |
| OpenSpec validate | `openspec validate "<name>"` |

API endpoints: `GET /health`, `POST /analyze`, `POST /analyze/batch`.
Swagger UI: `http://localhost:8000/docs`

---

## 3. Domain constraints (NON-NEGOTIABLE)

These are product/legal boundaries, not implementation preferences:

1. **Decision-support only** — every report is stamped accordingly; human
   review is required.
2. **No verification claims** — frame output as consistency analysis,
   not proof of location.
3. **National ID redaction** — detect presence/type only; never store or
   emit raw national-ID values.
4. **Offline enrichment only** — no third-party API calls that expose
   candidate PII (phone→country via libphonenumber, static TLD table).
5. **Four bands:** green / amber / red / gray (insufficient evidence).
   Sparse CVs must be gray, never silently green.
6. **Deterministic scoring** — pure rules + config weights; no LLM in the
   verdict path.

Weights and band thresholds: `apps/api/weights.yaml`. Tune via config, not
hard-coded magic numbers.

---

## 4. Code conventions

- **Minimize scope** — focused diffs; don't refactor unrelated code.
- **Match existing style** — read surrounding modules before adding code.
- **Library-first** — core logic in `apps/api/src/cv_validator/`; API is a thin
  wrapper in `apps/api/src/cv_validator/api/`.
- **Tests** — `apps/api/tests/` mirrors capabilities; fixtures in
  `apps/api/fixtures/calibration/`.
- **Env vars** for container/runtime config:
  - `CV_VALIDATOR_DB_PATH`
  - `CV_VALIDATOR_RETENTION_DAYS`
  - `CV_VALIDATOR_WEIGHTS_PATH`
- **Conventional Commits** — always use [Conventional Commits](https://www.conventionalcommits.org/)
  for git commit messages in this repo:
  - Format: `<type>[optional scope]: <description>` (imperative mood, lowercase
    subject, no trailing period; keep subject ≤ 72 chars).
  - Common types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`,
    `build`, `ci`, `chore`, `revert`.
  - Use `feat` for user-facing capability, `fix` for bug fixes, `chore` for
    tooling/config/docs-only housekeeping, `refactor` when behavior is unchanged.
  - Breaking changes: append `!` after type/scope or add a `BREAKING CHANGE:`
    footer.
  - Examples: `feat: add batch CV upload panel`, `fix: align sidebar header
    borders`, `chore: archive cv-location-consistency openspec change`.

Only create commits when explicitly asked.

---

## 5. OpenSpec workflow

This project uses [OpenSpec](https://github.com/Fission-AI/OpenSpec) with
the **spec-driven** schema.

```
openspec/
├── config.yaml          # Project context + per-artifact rules
├── specs/               # Source-of-truth specifications (after archive)
└── changes/<name>/      # Active change proposals
    ├── proposal.md
    ├── design.md
    ├── specs/
    └── tasks.md
```

**Workflow commands** (also available as skills/commands):

| Step | Cursor | Claude Code |
| --- | --- | --- |
| Propose | `/opsx-propose` | `.claude/commands/opsx/propose.md` |
| Implement | `/opsx-apply` | `.claude/commands/opsx/apply.md` |
| Explore | `/opsx-explore` | `.claude/commands/opsx/explore.md` |
| Archive | `/opsx-archive` | `.claude/commands/opsx/archive.md` |

Use OpenSpec for non-trivial features (new capabilities, API contracts,
scoring changes). Skip for pure tooling/config unless the user asks.

Active change: `cv-location-consistency` (implementation complete; ready
to archive when accepted).

---

## 6. Where to find what

| Topic | Location |
| --- | --- |
| Usage & Docker | `README.md` |
| Signal weights | `apps/api/weights.yaml` |
| Domain types | `apps/api/src/cv_validator/domain.py` |
| Ingestion (PDF/DOCX) | `apps/api/src/cv_validator/ingestion/` |
| Signal extractors | `apps/api/src/cv_validator/extraction/` |
| Scoring engine | `apps/api/src/cv_validator/scoring/engine.py` |
| FastAPI app | `apps/api/src/cv_validator/api/app.py` |
| Change proposal | `openspec/changes/cv-location-consistency/` |
| Calibration fixtures | `apps/api/fixtures/calibration/` |
| Cursor skills | `.cursor/skills/openspec-*/SKILL.md` |
| Claude skills | `.claude/skills/openspec-*/SKILL.md` |

---

## 7. When in doubt

Ask the user before:

- changing scoring weights or band logic without calibration fixtures,
- adding online enrichment or LLM-based verdicts,
- storing raw PII beyond what the audit spec allows,
- claiming the system "verifies" location.
