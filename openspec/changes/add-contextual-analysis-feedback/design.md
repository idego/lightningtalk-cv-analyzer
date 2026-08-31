## Context

FastAPI persists sanitized analyses in SQLite and Next.js uses Better Auth with
its own SQLite database. Both databases already live in persistent Docker named
volumes (`cv_validator_data` and `web_auth_data`). Production runs on a VPS and
the reviewed `main` branch is deployed automatically with Docker Compose.
Browser requests reach FastAPI through authenticated Next.js proxies using the
existing derived per-user analysis access token.

The feedback prototype established one compact morphing control, separate
helpful/not-helpful buttons, an auto-growing comment field, negative reason
pills, and a short send/reset animation. This change turns that interaction into
an owner-authorized persistent product feature.

## Goals / Non-Goals

**Goals:**

- Capture useful structured feedback at the exact output or persisted failure.
- Keep feedback context stable, bounded, private, and removable with analysis.
- Give a small group of internal reviewers a useful inbox without a general
  administration product or extra authorization library.
- Fit the existing VPS autodeploy and persistent-volume model.

**Non-Goals:**

- Editing reports, overriding scores, training automatically, or triggering AI,
  research, retry, or hiring actions.
- Raw-log upload/export, attachments, screenshots, conversation threads, CSV
  export, external feedback services, or arbitrary CV text annotation.
- Feedback on upload/parse errors before an owner-scoped analysis exists.

## Decisions

### 1. Materialize opaque targets on the server

`feedback_targets` stores an opaque UUID, `analysis_id`, closed target kind,
source category/key, and compact technical-version snapshot. Source keys use
existing code-owned IDs or closed structural coordinates; never display text,
filenames, candidate values, excerpts, or content hashes. Legacy reports get
targets only when mapping is unambiguous.

Supported kinds are review finding, structured fact, structural observation,
file detail, link result, company/education/LinkedIn research result,
operation failure, and report overall. A separate manifest maps targets to UI
items without mutating the canonical report JSON.

### 2. Keep feedback relational and tied to analysis lifecycle

The API database receives additive tables:

- `feedback_targets`
- `feedback_responses` with one current row per target and pseudonymous actor
- `feedback_events` without comment bodies
- `feedback_triage`
- `feedback_failure_context`

Actor and maintainer identifiers are keyed HMAC pseudonyms. Better Auth IDs and
emails are not copied into the API database. Manual deletion and retention purge
remove the full target/response/event/triage/diagnostic graph.

### 3. Reuse owner authorization and server-side proxies

Owner routes are scoped below an analysis and apply the existing analysis-access
check before target lookup:

- `GET /analyses/{analysis_id}/feedback`
- `PUT /analyses/{analysis_id}/feedback/{target_id}`
- `DELETE /analyses/{analysis_id}/feedback/{target_id}`

Next.js requires the Better Auth session and derives the analysis token
server-side. `PUT` is idempotent. The browser cannot submit target identity or
diagnostic context beyond the issued `target_id`.

### 4. Use the compact morphing control from the prototype

The closed 44px feedback button and open close-button share one anchored control
and geometry. Opening reveals equal-sized helpful/not-helpful controls, optional
negative reason pills, an initially one-line auto-growing comment field, and a
send icon. Escape and outside click close without submitting. Enter does not add
a newline or submit accidentally.

A normal submission is valid when it has a normalized 12–180 character comment,
or when `not_helpful` has one closed negative reason. This allows neutral
comment-only feedback and lets a negative reason replace prose. Helpful alone is
not sufficient. Concise accessible help explains that candidate data must not be
entered; there is no blocking privacy checkbox.

### 5. Attach a diagnostic reference, never logs

Persisted failures can materialize `operation_failure` for AI analysis/retry and
company, education, LinkedIn discovery, or LinkedIn comparison research. The
server-owned envelope contains only operation kind, normalized error code,
retryability, attempt count, occurrence time, correlation ID, and applicable
contract/model/prompt/schema versions.

The feedback API rejects client diagnostic keys. It never stores or displays raw
exception text, stack traces, HTTP bodies, prompts, model responses, research
queries/results/URLs, filenames, browser state, secrets, or candidate/report
content. Reviewers use correlation ID only as a reference to separately
protected operational logs. Missing legacy context becomes
`diagnostics_unavailable`; the system does not search broad logs as fallback.

Failure feedback records `not_helpful` plus `operation_failed`, allows an
optional comment, and never invokes retry.

### 6. Add scoped DB-backed reviewer access

The Better Auth database receives application-owned
`feedback_access(user_id, role, granted_by_user_id, created_at, revoked_at)`.
Roles are `owner` and `reviewer`. Reviewers inspect and triage; owners also grant,
change, and revoke access by exact existing verified email. The UI lists current
members, not the complete user directory, and prevents removal of the last owner.

The first owner is created once by a server-side bootstrap command for an
existing verified account. There is no browser bootstrap and no environment
email allowlist. Sidebar visibility is convenience only; every protected route
rechecks the active role.

Next.js calls FastAPI inbox endpoints with a separate high-entropy internal token
present only in both server environments. FastAPI compares it in constant time.

### 7. Keep the inbox narrow

The inbox offers cursor pagination, aggregate counts, closed filters, safe
target/version/failure context, sanitized comment, and triage states `new`,
`reviewing`, `planned`, `resolved`, and `wont_fix`. It never joins or
deserializes candidate audit payloads and has no report preview or export.

### 8. Make VPS deployment additive and restart-safe

API and web database initializers create their feedback tables and indexes
idempotently before serving traffic. The existing autodeploy on merge to `main`
builds replacement containers against the same named volumes. Deploy commands
must not use `docker compose down -v`, rename the Compose project, or recreate
the named volumes.

The first-owner bootstrap is a one-time operator action after the user's verified
login and is not repeated by CI. Feature controls remain disabled until schema,
server token, and owner bootstrap are present. A deploy enables backend storage
and owner APIs before exposing inbox navigation and failure controls. Rollback
disables UI/routes but leaves additive tables and data intact.

## Risks / Trade-offs

- Free-text PII can evade pattern matching: keep comments short, internal,
  sanitized, and coupled to retention.
- A correlation ID can lead to sensitive logs: expose it only to authorized
  reviewers and keep log access outside this subsystem.
- Lost reviewer ownership can lock administration: reject last-owner removal and
  retain an explicit server-side owner recovery command.
- Container replacement can hide migration mistakes: use idempotent startup
  schema changes on persistent volumes and never destructive rollback.
- Feedback volume may be small: present counts and categorized entries, not an
  “accuracy” metric.

## Migration Plan

1. Add idempotent API feedback schema and web feedback-access schema.
2. Add configuration and internal server token to the VPS secret environment.
3. Deploy disabled through the normal merge-to-`main` autodeploy and confirm both
   existing named volumes remain attached.
4. Have the first owner sign in, then run the one-time bootstrap command on the
   VPS for that verified account.
5. Enable owner feedback capture, then inbox navigation and failure feedback.
6. Roll back with feature controls and the previous reviewed image/commit; do not
   delete volumes or feedback tables.

## Open Questions

None blocking implementation. Exact Polish labels and final icon stroke details
may be polished without changing the contracts above.
