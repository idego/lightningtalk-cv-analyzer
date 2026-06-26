## Why

We are adding a Next.js frontend alongside the existing FastAPI backend, turning this single-service repo into a two-service product. Before any frontend work, the repository must be reorganized so each service has a clear home and the backend's frozen HTTP contract is preserved. Tracks [#1](https://github.com/idego/lightningtalk-cv-analyzer/issues/1).

This is a **structural refactor only** — files move, build/run wiring is updated, and no backend behavior, scoring, or API surface changes.

## What Changes

- Move the entire Python backend from the repo root into `apps/api/` (`src/`, `tests/`, `fixtures/`, `weights.yaml`, `pyproject.toml`, `Dockerfile`, `.dockerignore`).
- Add an `apps/web/` placeholder for the frontend (real scaffold lands in a later change).
- Update backend build/test wiring for the new location (`pyproject.toml` pytest `pythonpath` + hatch packages, `Dockerfile` COPY/context paths).
- Update the root `docker-compose.yml` build contexts so the backend builds from `apps/api/` (full web+api orchestration is a later change).
- Update docs and tooling references to the new paths: `AGENTS.md`, `CLAUDE.md`, `README.md`, the workflow skills, and any path-based references under `openspec/`.

## Capabilities

### New Capabilities
- `monorepo-structure`: Defines the two-service repository layout (`apps/api`, `apps/web`), the requirement that the backend's API contract and test suite remain unchanged after the move, and that build/run wiring resolves from the new locations.

### Modified Capabilities
<!-- None. The CV-analyzer behavioral capabilities are unchanged; this change only relocates their implementation. -->

## Impact

- **Moved:** `src/cv_validator/` → `apps/api/src/cv_validator/`; `tests/` → `apps/api/tests/`; `fixtures/calibration/` → `apps/api/fixtures/calibration/`; `weights.yaml`, `pyproject.toml`, `Dockerfile`, `.dockerignore` → `apps/api/`.
- **Added:** `apps/web/.gitkeep` placeholder.
- **Edited:** root `docker-compose.yml` (build contexts), `AGENTS.md`, `CLAUDE.md`, `README.md`, workflow skills, `openspec/` path references.
- **Unchanged:** all backend logic, scoring, weights values, and the `/health`, `/analyze`, `/analyze/batch` contract.
- **Out of scope:** frontend code, auth, full compose orchestration, deployment (separate issues #3–#6).
