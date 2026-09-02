# Operations

## Runtime

- This branch installs exactly one `docling-luna` strategy and exposes its name
  and version through health and every report.
- `OPENAI_API_KEY` is required when public research or a Luna strategy is
  enabled. Never commit the key.
- Let the one-shot `geonames-init` service build and validate both GeoNames
  index/manifest pairs in its persistent volume. The API mounts the promoted
  release read-only, and runtime CV analysis never downloads reference data.
- For an approved offline snapshot, use `REFERENCE_DATA_MODE=operator`; see
  `docs/reference-data/geonames.md` for refresh and recovery procedures.
- Keep only the web service public. The API stays on the internal Compose
  network.
- Persist and back up the API and authentication SQLite volumes.
- Configure retention with `CV_VALIDATOR_RETENTION_DAYS`.

The browser setting controls optional public company, education, and LinkedIn
research. It does not disable the selected base-analysis strategy.

## Contextual feedback rollout

Feedback is decision-neutral and never edits a report, analysis output,
research result, retry state, or hiring action. Targets and responses live with
the analysis in `cv_validator_data`; reviewer roles live with Better Auth in
`web_auth_data`. Comments are limited to 180 characters, contact details and
URLs are rejected, and inbox entries contain no CV text, prompt/model output,
research content, filenames, raw exceptions, request bodies, or logs.

Use this one-time production sequence:

1. Back up both named volumes and deploy with all three feedback flags `false`.
2. Set independent high-entropy `CV_VALIDATOR_FEEDBACK_HMAC_SECRET` and
   `CV_VALIDATOR_FEEDBACK_INTERNAL_TOKEN` values in the VPS secret `.env`.
3. Let the first owner sign in and verify their email, then run
   `docker compose --env-file .env exec web pnpm feedback:bootstrap-owner exact@idego.io`.
4. Enable `CV_VALIDATOR_FEEDBACK_ENABLED`, deploy and verify capture.
5. Enable `CV_VALIDATOR_FEEDBACK_INBOX_ENABLED`, then
   `CV_VALIDATOR_FEEDBACK_FAILURES_ENABLED`, verifying health after each step.

Owners grant or revoke `owner`/`reviewer` access by exact verified email in the
Feedback access page. The last active owner cannot be removed there; recover
ownership with the same server-side command. The API bounds a pseudonymous
actor to 30 writes per minute. Reviewers may use a correlation ID only to find
separately protected operational logs; it is not an invitation to copy logs
into feedback.

To disable the feature, set the three flags to `false` and redeploy. For an
application rollback, check out the previous reviewed SHA and run `make deploy`.
Both paths preserve additive tables and both existing named volumes. Never use
`docker compose down -v`, rename the Compose project, or delete/recreate either
volume. Rotate both feedback secrets by disabling writes/inbox, replacing the
values together in the VPS secret configuration, redeploying, and re-enabling;
rotation changes future pseudonyms and invalidates the old server token.

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
