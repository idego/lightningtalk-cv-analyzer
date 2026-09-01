# Operations

## Runtime

- This branch installs exactly one `docling-luna` strategy and exposes its name
  and version through health and every report.
- `OPENAI_API_KEY` is required when public research or a Luna strategy is
  enabled. Never commit the key.
- Mount the validated GeoNames index and manifest; runtime analysis never
  downloads reference data.
- Keep only the web service public. The API stays on the internal Compose
  network.
- Persist and back up the API and authentication SQLite volumes.
- Configure retention with `CV_VALIDATOR_RETENTION_DAYS`.

The browser setting controls optional public company, education, and LinkedIn
research. It does not disable the selected base-analysis strategy.

## Canonical commands

```bash
make dev
make dev-down
```

The command uses Compose project `cv-analyzer-docling-luna`, loopback web port
3021, API database `/app/data/docling_luna.db`, and auth database
`/app/data/docling_luna_auth.db`.

Production deploys an exact reviewed SHA:

```bash
make deploy-check
make deploy
```

The reverse proxy terminates TLS and forwards only to the loopback-bound web
port. Readiness requires the selected variant strategy; degraded optional
research capabilities remain visible individually.

## Data and logs

- Raw uploads are processed in memory and are not persisted.
- Audit JSON contains the validated report, not the ownership token.
- Logs may contain identifiers, status, duration, and safe error codes only.
- Never log CV text, evidence excerpts, model output, secrets, or local paths.
- Research cache audit records expose hit, partial-hit, miss, refresh, and
  per-subject provenance to the owner.
- Back up SQLite using an online backup or while the stack is stopped.
- Restore rehearsals use a separate Compose project, ports, volumes, and
  database paths.

## Failure and rollback

A strategy failure returns a bounded per-document error. It must not silently
fall back to a different strategy or the removed deterministic pipeline.

For application rollback, deploy the previously recorded reviewed SHA. Named
volumes remain intact. This variant uses `docling_luna.db` and does not migrate
old pilot reports. Never delete an existing database implicitly.
