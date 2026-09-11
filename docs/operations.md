# Operations

## Runtime

- The API installs exactly one `document-analysis` strategy and exposes its name
  and version through health and every report.
- `OPENAI_API_KEY` is required when public research or the model-backed analysis is
  enabled. Never commit the key.
- Let the one-shot `geonames-init` service build and validate both GeoNames
  index/manifest pairs in its persistent volume. The API mounts the promoted
  release read-only, and runtime CV analysis never downloads reference data.
- For an approved offline snapshot, use `REFERENCE_DATA_MODE=operator`; see
  `docs/reference-data/geonames.md` for refresh and recovery procedures.
- Keep only the web service public. The API stays on the internal Compose
  network in production; `make dev` adds `docker-compose.dev.yml`, which
  publishes it on `127.0.0.1:8001` for Swagger only.
- Persist and back up the API and authentication SQLite volumes.
- Configure retention with `CV_VALIDATOR_RETENTION_DAYS` (1-3650 days; the
  API refuses to start outside that range).

Retention is enforced by a background maintenance loop, not only on request
paths. The API purges expired analyses and Profile Builder profiles once at
startup and then every 24 hours while running; on Saturdays it also runs one
SQLite `VACUUM` so freed pages leave the database file. All connections set
`PRAGMA secure_delete` so deleted rows are zeroed rather than left in free
pages. `GET /operations/status` exposes the loop state under
`retention.maintenance`. A failed startup or scheduled purge sets the
`retention_purge` capability on `GET /health` to not ready with reason
`retention_purge_failed`, which also flips top-level `ready` to false so the
Compose healthcheck marks the container unhealthy; the flag clears on the
next successful purge.

The browser setting controls optional public company, education, and LinkedIn
research. It does not disable the selected base-analysis strategy.

## Contextual feedback rollout

Feedback is decision-neutral and never edits a report, analysis output,
research result, retry state, or hiring action. Targets and responses live
in `cv_validator_data`; reviewer roles live with Better Auth in
`web_auth_data`. Analysis data is transient and recruiter-owned, whereas
feedback is long-lived platform and review data that survives analysis deletion
and retention purge, similar to the AI usage ledger. Normal report deletion
(`DELETE /analyses/{id}`, `DELETE /analyses`) and retention purge leave feedback
targets, reviewer responses, triage notes, displayed context snapshots, and
diagnostic failure context intact. The retained `analysis_id` is kept as a
historical correlation identifier. Feedback is enabled by default. Responses
retain the signed-in author's email and a snapshot of the displayed CV/report
section (label up to 200 characters, text up to 12000 characters, and the
report JSON up to 400000 serialized characters) so the inbox can re-render the
referenced report section with the same components as the analysis view, even
after the analysis itself is gone. Each inbox item carries
`analysis_available`; when the analysis was deleted and no report snapshot
exists, the inbox shows the section name in place of the report section. Comments are 12 to 300 characters; team
notes are limited to 500 characters; contact details and URLs are rejected from
both. The web proxy caps a feedback write at 512 KiB and a triage note at 2
KiB. The inbox never stores the uploaded original, raw model output, raw
exceptions, request bodies, or logs.

Access is initialized automatically by the one-shot `feedback-init` Compose
service from `apps/web/config/feedback-access.json`, which is included in the
initializer image at build time. It seeds the initial owners only when the
access table is empty; later deploys never restore access changed in the UI.
Both `feedback-init` and `web` read `BETTER_AUTH_DB_PATH`, so an
override applies to both. With `LOCAL_DEV_AUTH_BYPASS=true` (`make dev`), the
service also grants `local-dev@localhost` an owner role on every run.
Operations endpoints `GET /operations/metrics` and `GET /operations/status`
expose telemetry counters and strategy status inside the Compose network.

Use this production sequence:

1. Back up both named volumes.
2. Deploy and verify that `feedback-init` completed successfully.
3. Sign in with one of the configured owner addresses and verify capture and
   inbox access. Owners can then enable or disable new feedback in the panel.

Owners grant or revoke `owner`/`reviewer` access by exact allowed-domain email
in the Feedback access page; access applies when that address signs in. The
same page controls collection of new feedback without disabling the historical
inbox. The last active owner cannot be removed. The API bounds a pseudonymous
actor to 30 writes per minute. Reviewers may use a correlation ID only to find
separately protected operational logs; it is not an invitation to copy logs
into feedback.

Disabling collection in the owner panel preserves existing feedback and inbox
access. For an application rollback, check out the previous reviewed SHA and
run `make deploy`. Both paths preserve additive tables and both existing named volumes. Never use
`docker compose down -v`, rename the Compose project, or delete/recreate either
volume.

## Canonical commands

```bash
make dev
make dev-down
```

The command uses Compose project `cv-analyzer`, published web port 3000, API
database `/app/data/cv_analyzer.db`, and auth database `/app/data/auth.db`.
Named volumes are keyed by the project name, so do not change it casually. A
stack created under the former project `cv-analyzer-document-analysis` with the
former `docling_luna.db` / `docling_luna_auth.db` defaults keeps its data only
if you run with `COMPOSE_PROJECT_NAME=cv-analyzer-document-analysis` and pin
`CV_VALIDATOR_DB_PATH` and `BETTER_AUTH_DB_PATH` to those paths in the env
file, or copy the volumes to the new project once while the stack is stopped.


Container resource limits are bounded in Compose and can be overridden with the documented `WEB_*`, `API_*`, and `GEONAMES_INIT_*` resource variables. Runtime images execute as non-root users. `GEONAMES_SNAPSHOT_VERSION` must match `config/geonames.lock`; changing the snapshot requires intentionally refreshing the lock and reference data together.

Production deploys an exact reviewed SHA:

```bash
make deploy-check
make deploy
```

The reverse proxy terminates TLS and forwards to the published web
port. Readiness requires the selected variant strategy; degraded optional
research capabilities remain visible individually.

## AI usage accounting

The Dashboard shows authenticated deployment-wide lifetime accounting from the
append-only usage ledger, not by summing mutable report or research rows. A
completed or partial base report increments `processed_report_events` once; failed AI
attempts may still contribute tokens/cost without increasing report throughput.
Each successful paid provider response is ledgered before mutable result/cache
persistence. Provider retries therefore count as separate paid attempts, while
an idempotent repeat of the same event key is ignored. Reusable company and
education cache hits make no new paid usage event; the original cache-miss
provider request remains counted once.

Costs are estimates. Input tokens are priced in three tiers as reported by the
provider: uncached, cached reads (`cached_input_tokens`), and prompt-cache
writes (`cache_write_input_tokens`, billed above the uncached rate on GPT-5.6
models). Each request carries a per-pass `prompt_cache_key` so repeated
prefixes route to the same cache; the key never changes model output. Each
usage row stores the pricing catalog version and its computed USD cost, plus the fixed conversion rate/version and derived PLN cost.
The current fixed conversion is `1 USD = 3.75 PLN`; no live exchange-rate fetch
is used and historical rows are never repriced when code/config changes. The
pricing catalog can be overridden with `CV_VALIDATOR_PRICING_PATH`; changing it
must use a new catalog version.

Normal report deletion and retention intentionally preserve `ai_usage_events`;
its retained `analysis_id` is only a pseudonymous accounting correlation key.
`processed_report_events` is deleted together with the analysis, so the
Dashboard's processed-report count and per-report averages cover retained
analyses only. Report/audit/research rows are deleted according to normal
lifecycle rules. The ledger must never contain CV
text, evidence, prompts, model responses, candidate data, e-mail addresses, or
other PII. The API is internal-only; browser access to deployment totals goes
through the authenticated web route, and per-report totals additionally require the
authenticated web user to own the analysis by stable Better Auth user id.

## Data and logs

- After a report is committed, its original PDF/DOCX is retained only for the configured analysis-retention window so the owner can reopen the preview; it is deleted with the analysis or retention purge.
- Audit JSON contains the validated report and never contains ownership credentials or internal owner ids.
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
volumes remain intact. The API uses `cv_analyzer.db` and does not migrate
old pilot reports. Never delete an existing database implicitly.


## Profile Builder runtime

Rebuild the API image when enabling the restored Profile Builder; it installs
`libreoffice-writer` and `fonts-liberation`. Non-container installs need a `soffice`
or `libreoffice` executable on PATH for PDF output. Conversion uses a fresh
LibreOffice user directory per request and a 30-second timeout. No external
conversion service is used.

`GET /health` exposes independent `profile_builder` and `profile_pdf_export`
capabilities. AI conversion/edits need the existing configured provider key; PDF
export needs LibreOffice. DOCX download and saved-profile editing remain available
without AI. The API remains internal: browsers use `/api/profile-builder/*`.

The web build uses Node 22.13 or newer and prepares a same-origin PDF.js worker and
WASM assets from the pinned package via `scripts/prepare-pdf-worker.mjs`. They are
copied into `public/pdfjs` during `pnpm dev` / `pnpm build`; generated vendor files
are not committed. Include `public` when distributing standalone builds, as the
existing Docker build already does. No CDN receives profile data.

Profile retention follows the existing configured retention period, using the
profile's last-updated timestamp. Deleting an analysis does not delete a separately
saved editable profile. Back up the existing API database to include profiles,
templates, custom fields, and preferences. No new database service is required.


## Consolidated-branch upgrade

Before the first upgrade from the token-owned `base-analysis-v2` database, stop
writes and back up both application and authentication volumes. Deploy web and
API together; their internal owner header changes as one contract. Do not rotate
`BETTER_AUTH_SECRET` during this first upgrade. Existing hashes move into a
transient `legacy_analysis_owners` mapping instead of being discarded. On an
authenticated request, the private API derives that user's old HMAC and binds
only matching reports/runs to the stable Better Auth user id. Original uploads,
share links, feedback snapshots, authorship, triage and events are retained.
Repeated or concurrent binding is safe. Normal retention also removes unclaimed
migration mappings; it continues to retain feedback and the AI usage ledger.

When rotating the authentication secret before every retained owner has returned,
set `CV_VALIDATOR_LEGACY_OWNER_SECRET` to the original secret in the API environment.
Already bound analysis ownership is independent of secret rotation. Profile Builder
still uses its original server-only HMAC namespace for existing profiles, templates
and preferences, so preserve its original auth secret until those records have a
separately planned ownership migration. No owner token is returned to the browser.
Databases already upgraded by dropping hashes without preserving a mapping need a
pre-upgrade backup to recover ownership; this migration cannot reconstruct a lost
secret or unknown user identity.

The `volume-init` one-shot container fixes ownership of the two existing named
application volumes before API and feedback initialization start. It runs as root
only for this operation; API runs as UID/GID 10001 and the web/feedback initializer
as UID/GID 1000. This covers existing root-owned SQLite databases, not just fresh
empty volumes. It also marks existing GeoNames release files readable (`a+rX`):
earlier bootstraps published them `0600 root`, which the non-root API cannot open,
so `/health` reported `geonames_unavailable` and the container stayed unhealthy.
Do not replace it with world-writable permissions or expose the API.
Custom database paths must stay within their respective `/app/data` mounts.

The GeoNames version must match `config/geonames.lock` (`2026-08-21` for this
snapshot); update old environment files that still use `2026-09-02`, or intentionally
refresh both the approved data and lock together. The web host port remains 3000
by default and the container still listens on 3000.

A code-only checkout of an older token-owned version is not a database rollback.
Restore the backed-up volumes together with that version. Never delete volumes to
make an upgrade pass.
