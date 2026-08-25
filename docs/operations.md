# V1 operations guide

The AI feature is enabled for the accepted local development stack. Production
enablement still requires wider-corpus, HR-criteria and stakeholder approval.

## Configuration and reference data

- `CV_VALIDATOR_AI_ENABLED=false`; `OPENAI_API_KEY` is required only when enabled.
- Model timeout: 120 s; provider-SDK retries: 0; max output: 4096 tokens.
- Application retry defaults: `CV_VALIDATOR_AI_TRANSPORT_RETRY_LIMIT=1`,
  `CV_VALIDATOR_AI_INVALID_RESPONSE_RETRY_LIMIT=1`, and
  `CV_VALIDATOR_AI_ABSOLUTE_ATTEMPT_LIMIT=3`. Timeouts, network errors, 429,
  and 5xx are transport-retryable; other 4xx responses are not.
- `CV_VALIDATOR_BATCH_MAX_FILES=4`, `CV_VALIDATOR_BATCH_MAX_BYTES=20971520`.
- `CV_VALIDATOR_RESEARCH_CACHE_TTL_DAYS=30` controls the provisional public-fact cache TTL.
- `CV_VALIDATOR_RETENTION_DAYS=90` is the default development retention value.
  The effective value is configurable in Settings and persisted in SQLite, so
  deployment does not require a separate hard-coded production value.
- Local validation has a USD 1 soft budget and USD 2 hard stop. Runtime requests
  are bounded by file, output-token and Web Search limits; production must also
  use an OpenAI project budget because a request cannot be unspent after it
  completes.
- GeoNames paths must be an approved local index/manifest pair; refresh is manual and reviewed. Analysis never downloads reference data.

## Cache and retention

Only normalized public company/institution/program/certificate subjects and
allowlisted public-web facts are reusable. Keys include cache, research,
prompt, schema, model and search-policy versions. Candidate identity, analysis
ID, CV evidence, candidate relations, contact values and national IDs are not
cache material. Hits/misses are recorded against the requesting analysis.
Entries expire independently and an operator can invalidate one/all through
`PersistenceStore.invalidate_reusable_research`; restart is not required.
`PersistenceStore.purge_expired()` returns per-table deletion counts. The one
effective retention value covers the complete candidate-analysis graph:
reports, audit data, AI results and candidate-scoped company, education and
LinkedIn research. Reusable public-entity research has its own cache TTL because
it contains no candidate data.

The API never writes upload bytes to a file or database. It parses in memory,
masks national IDs before downstream output, and persists a redacted canonical
text hash. SQLite contains reports, safe audit records and validated results.

## Monitoring and failure modes

`GET /operations/status` exposes effective non-secret limits and approval
state. `GET /operations/metrics` exposes request totals/duration totals,
research failures and cache hits/misses. Logs are structured JSON containing
only correlation/analysis IDs, category, status, duration and safe error codes;
never request bodies, access capabilities, CV evidence or API keys.

Timeout/invalid/client failures return retryable bounded category errors and do
not persist partial completion. Cache expiry may cause duplicate external work
across processes; SQLite upsert remains idempotent, while V1 process-local locks
coalesce concurrent calls inside one synchronous API process.

Base-report AI failures persist only safe stage/status/request/attempt/latency
metadata. CV text, model output, secrets, and filesystem paths are excluded.
The deterministic report remains available. Manual Retry reuses a redacted
process-memory context, calls only Document Analyzer, and never starts research
or changes deterministic score/band. The context is removed after success,
owner deletion, retention cleanup, or process restart; after restart the UI
honestly reports that manual retry is unavailable.

## Runbooks and rollback

Local: keep AI disabled, run backend/frontend tests, then inspect status and
metrics. Production: mount persistent SQLite, review the effective retention
in Settings, configure reference data and secrets, keep only the web service public, back up SQLite,
and alert on research/model failure ratios and sustained latency.

Deterministic-only rollback: set `CV_VALIDATOR_AI_ENABLED=false` and restart the
API. Upload analysis continues with the new code-owned facts and unchanged
deterministic score/band; research endpoints return disabled. Never roll back
by changing weights or thresholds. If a schema migration is suspect, stop
writes, preserve a SQLite backup, roll back the application image, and validate
readability before resuming.

Architecture escalation is **not triggered** for V1. Three live CVs completed
through the local Docker path with zero failures and about one cent of model
cost. Existing four-case measurements also fit the synchronous request limit.
