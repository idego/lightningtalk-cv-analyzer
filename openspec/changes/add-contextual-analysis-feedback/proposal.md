## Why

Recruiters can inspect CV Analyzer output but cannot report whether a specific
finding, fact, research result, or failure was useful or wrong where they
encounter it. Informal reports lack stable target identity, technical versions,
and safe diagnostic context, so recurring product and AI problems are difficult
to group and repair.

Persisted AI-analysis and research failures are especially opaque. Users should
be able to report them without copying console output or exposing CV content,
prompts, model responses, secrets, or raw logs.

## What Changes

- Add a compact contextual feedback control to supported report items and one
  overall-report location.
- Support helpful, not-helpful, and comment-only feedback. A regular submission
  requires a 12–180 character comment, except that a closed negative reason may
  justify not-helpful feedback without prose.
- Bind feedback to server-materialized owner-scoped targets rather than browser
  display text, array positions, or copied report content.
- Add feedback beside persisted AI-analysis and research failures. The server
  attaches a closed diagnostic envelope and opaque correlation ID; raw logs are
  never uploaded through feedback.
- Persist feedback in SQLite with analysis retention/deletion, idempotent
  update/withdraw semantics, comment sanitization, and no scoring authority.
- Add an internal feedback inbox with simple triage.
- Store `owner` and `reviewer` access against existing Better Auth users. Owners
  manage access in-product; the first owner is bootstrapped once by a server-side
  command. Authorized users see a conditional Feedback sidebar entry.
- Deploy through the existing VPS Docker Compose autodeploy after merge to
  `main`, using the existing persistent named volumes and additive startup
  migrations.

## Capabilities

### New Capabilities

- `contextual-analysis-feedback`: Owner-scoped feedback capture, safe target and
  failure diagnostics, persistence, reviewer access, inbox triage, privacy, and
  lifecycle boundaries.

### Modified Capabilities

- `frontend-analysis-workflow`: Supported report items and persisted AI/research
  failures gain a minimal contextual feedback interaction.

## Impact

- API: additive feedback tables, target materialization, owner endpoints,
  internal inbox endpoints, failure diagnostic snapshots, and purge integration.
- Web: feedback proxies and component, target mapping, DB-backed reviewer roles,
  conditional sidebar navigation, inbox, and access management.
- Operations: new feedback feature settings and internal admin token; additive
  migrations must run safely during VPS replacement deploys without recreating
  or deleting `web_auth_data` or `cv_validator_data`.
- Existing reports remain compatible. Feedback cannot change report content,
  deterministic scores/bands, AI prompts/results, research, retry behavior, or
  hiring decisions.
- No external feedback vendor, full RBAC library, new AI call, or online PII
  enrichment is introduced.
