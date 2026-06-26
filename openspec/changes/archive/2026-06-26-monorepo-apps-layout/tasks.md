## 1. Move backend into apps/api

- [x] 1.1 `git mv` `src/`, `tests/`, `fixtures/` into `apps/api/`
- [x] 1.2 `git mv` `weights.yaml`, `pyproject.toml`, `Dockerfile`, `.dockerignore` into `apps/api/`
- [x] 1.3 Confirm no backend source remains at the repo root

## 2. Fix backend build/test wiring

- [x] 2.1 Update `apps/api/pyproject.toml` `[tool.pytest.ini_options].pythonpath` and `[tool.hatch.build.targets.wheel].packages`
- [x] 2.2 Update `apps/api/Dockerfile` COPY paths for the `apps/api/` build context
- [x] 2.3 Verify `CV_VALIDATOR_DB_PATH` / `CV_VALIDATOR_WEIGHTS_PATH` defaults still resolve (adjust only if a default encodes a moved path)

## 3. Update root orchestration

- [x] 3.1 Update root `docker-compose.yml` so the `api`/`test` services build from `apps/api/`
- [x] 3.2 Add `apps/web/.gitkeep` placeholder

## 4. Update docs and tooling references

- [x] 4.1 Update `AGENTS.md` (file map, commands, "where to find what")
- [x] 4.2 Update `CLAUDE.md` if it references moved paths
- [x] 4.3 Update `README.md` commands and paths
- [x] 4.4 Reconcile workflow skills' monorepo check paths (`apps/api`, `apps/web`)
- [x] 4.5 Grep for stale root-path references (`src/`, `tests/`, `weights.yaml`) and fix

## 5. Verify (acceptance)

- [x] 5.1 `cd apps/api && PYTHONPATH=src pytest` — all 28 tests pass
- [x] 5.2 `docker compose --profile test run --rm test` passes from new layout
- [x] 5.3 Backend image builds from `apps/api/` context and `/health` responds
- [x] 5.4 Confirm `/analyze` and `/analyze/batch` behavior unchanged
