# Operations

## Runtime

- The shared cleanup branch intentionally reports degraded health because no
  base-analysis strategy is installed.
- Each experiment must install exactly one strategy and expose its name and
  version through health and every report.
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
cp .env.example .env.local
make dev ALLOW_DEGRADED=true  # shared base only
make dev-down
```

Variant branches must use plain `make dev`; degraded readiness is not accepted
once a concrete strategy is installed.

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
- Research cache audit records must expose hit/miss provenance to the owner.
- Back up SQLite using an online backup or while the stack is stopped.
- Restore rehearsals use a separate Compose project, ports, volumes, and
  database paths.

## Failure and rollback

A strategy failure returns a bounded per-document error. It must not silently
fall back to a different strategy or the removed deterministic pipeline.

For application rollback, deploy the previously recorded reviewed SHA. Named
volumes remain intact. The reset uses `cv_analyzer_v2.db` and does not migrate
old pilot reports. Never delete an existing database implicitly.
