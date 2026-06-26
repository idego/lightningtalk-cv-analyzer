## Context

The repo currently is the backend: Python package at `src/cv_validator/`, tests at `tests/`, plus `weights.yaml`, `pyproject.toml`, `Dockerfile`, and a `docker-compose.yml` that builds from the root. A frontend is coming, so we need a two-service layout. The backend contract is frozen (issue #1), so this change must be behavior-preserving.

## Goals / Non-Goals

**Goals:**
- A clear `apps/api` + `apps/web` monorepo layout.
- Backend builds, runs, and tests identically from its new location.
- All path references (docs, compose, tooling) point at the new locations.

**Non-Goals:**
- No backend behavior, scoring, weights, or API changes.
- No frontend implementation (placeholder only).
- No full web+api compose orchestration or deployment (issue #6).

## Decisions

### D1: `apps/<service>` layout
Use `apps/api` and `apps/web` (chosen in planning) over `services/` or `backend/`+`frontend/`. Conventional monorepo naming; leaves room for shared `packages/` later if needed.

### D2: Backend keeps its own `pyproject.toml`, `Dockerfile`, build context
Each service stays self-contained and independently buildable. The backend's Docker build context becomes `apps/api/`. No root-level Python tooling. **Alternative considered:** a root workspace/monorepo tool — rejected as overkill for two loosely-coupled services in different languages.

### D3: Move with `git mv` to preserve history
Use `git mv` so blame/history follow the files. Verify nothing references the old root paths afterward.

### D4: Behavior-preserving — verify by the existing test suite
The 28-test suite is the contract guard. It must pass from `apps/api` (`cd apps/api && PYTHONPATH=src pytest`) and via the relocated `test` compose profile, with zero source changes beyond import/path wiring (there should be none, since imports are package-relative).

## Risks / Trade-offs

- **Stale path references** (Dockerfile COPY, compose context, pytest `pythonpath`, docs) → Grep for `src/`, `tests/`, `weights.yaml`, root `Dockerfile` references after the move; rely on the test suite + a Docker build to catch misses.
- **Root `docker-compose.yml` half-migrated** (api moved, web not yet) → Keep compose minimal here (api building from `apps/api`); defer the web service + private-network wiring to issue #6 so this change stays focused.
- **`data/` volume / DB path drift** (`CV_VALIDATOR_DB_PATH`) → Keep env-var defaults and volume semantics identical; only adjust if a default encodes a now-moved path.

## Migration Plan

1. `git mv` backend files into `apps/api/`.
2. Fix `pyproject.toml` (`pythonpath`, hatch packages) and `Dockerfile` paths.
3. Update root `docker-compose.yml` build context for `api`.
4. Update `AGENTS.md`, `CLAUDE.md`, `README.md`, workflow skills, `openspec/` references.
5. Add `apps/web/.gitkeep`.
6. Verify: `cd apps/api && PYTHONPATH=src pytest` green; `docker compose --profile test run --rm test` green; Docker image builds.

Rollback: revert the branch; no data migration involved.

## Open Questions

- Should the root keep a thin convenience `docker-compose.yml`, or wait for issue #6 to author the full stack? (Leaning: minimal api-only compose now, full orchestration in #6.)
