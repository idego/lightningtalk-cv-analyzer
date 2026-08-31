## 1. Contracts and target identity

- [ ] 1.1 Add closed backend contracts for target kinds, nullable rating,
  reasons, current feedback state, failure diagnostics, triage, filters, and
  pagination, including the 12–180 comment validity rules.
- [ ] 1.2 Implement server target materialization for new reports using existing
  code-owned IDs or content-free structural keys.
- [ ] 1.3 Add conservative lazy target materialization for retained reports and
  omit ambiguous mappings.
- [ ] 1.4 Add typed frontend manifest/feedback contracts and helpers mapping
  server targets to rendered report and failure items.

## 2. API persistence and lifecycle

- [ ] 2.1 Add idempotent SQLite initialization for feedback targets, responses,
  comment-free events, triage, and failure context with required indexes and
  uniqueness constraints.
- [ ] 2.2 Add actor/maintainer HMAC pseudonymization and bounded feedback/internal
  note normalization, PII detection, redaction, and rejection.
- [ ] 2.3 Implement current-response create/update/read/withdraw operations and
  minimal withdrawal tombstones.
- [ ] 2.4 Materialize closed failure diagnostics from persisted AI-analysis/retry
  and company/education/LinkedIn research failures.
- [ ] 2.5 Extend single-analysis deletion, delete-all, and retention purge to the
  complete feedback graph.

## 3. Owner feedback API and web proxies

- [ ] 3.1 Add owner-authorized manifest/read-back, idempotent PUT, and withdrawal
  DELETE routes below `/analyses/{analysis_id}` using the existing access check.
- [ ] 3.2 Enforce target-analysis binding, closed input, request/comment limits,
  per-actor write limits, and rejection of all client diagnostic/log fields.
- [ ] 3.3 Add session-protected Next.js proxy routes that derive and forward the
  existing analysis access token server-side.
- [ ] 3.4 Add feedback feature/comment settings, safe defaults, and health
  capability reporting without affecting analysis availability.
- [ ] 3.5 Add aggregate-safe operational logging limited to templated operation,
  outcome, target kind, closed classification, and latency.

## 4. Feedback control and report integration

- [ ] 4.1 Turn the approved single-file prototype into a reusable CV Analyzer
  feedback component using the application's font, button geometry, colors, and
  motion tokens without adding a new UI or animation dependency.
- [ ] 4.2 Implement the anchored 44px bubble-to-close morph, helpful/not-helpful
  controls, neutral flow, negative reason pills, auto-growing 180-character
  comment, remaining counter, send animation, success reset, Escape/outside
  close, focus restoration, and reduced-motion behavior.
- [ ] 4.3 Load the feedback manifest once per persisted report and restore the
  current user's selections and drafts without per-item request fan-out.
- [ ] 4.4 Integrate feedback targets with review findings, structured facts,
  structural observations, file/link details, supported research results, and
  one overall-report location.
- [ ] 4.5 Add “Zgłoś problem” to server-targeted AI-analysis/retry and
  company/education/LinkedIn failure states while keeping retry separate.
- [ ] 4.6 Keep controls absent from upload/loading, pre-persistence errors,
  static disclaimers, CV preview content, and items without safe targets.

## 5. Reviewer authorization and inbox

- [ ] 5.1 Add idempotent initialization of the `feedback_access` table in the
  existing Better Auth SQLite database with `owner` and `reviewer` roles.
- [ ] 5.2 Add a server-side command to bootstrap/recover an owner by exact
  existing verified email, with no browser-accessible bootstrap path.
- [ ] 5.3 Add server authorization helpers, conditional Feedback sidebar entry,
  and protected inbox/access proxy routes.
- [ ] 5.4 Add owner-only access management for exact-email grant, role change,
  revoke, current-member listing, and last-owner protection.
- [ ] 5.5 Add constant-time internal-token authentication to FastAPI inbox and
  triage routes; keep the token server-to-server and out of browser responses.
- [ ] 5.6 Build the internal inbox with counts, closed filters, cursor pagination,
  safe target/version/failure context, sanitized details, and the five triage
  states, without joining report/audit payloads or adding export.

## 6. VPS rollout and documentation

- [ ] 6.1 Add feedback settings and the internal admin token to production
  environment examples and the VPS secret configuration used by autodeploy.
- [ ] 6.2 Ensure web/API startup applies additive schema initialization before
  serving traffic and continues to mount `web_auth_data` and
  `cv_validator_data` under the existing Compose project.
- [ ] 6.3 Update deployment automation so merge-to-`main` replacement deploys do
  not remove volumes and deploy feedback disabled until configuration exists.
- [ ] 6.4 Document the one-time VPS sequence: deploy, sign in the first verified
  owner, run bootstrap, enable capture, then enable inbox/failure feedback.
- [ ] 6.5 Document feature disablement and previous-release rollback without
  dropping tables, volumes, or retained feedback.
- [ ] 6.6 Update README and operations guidance for privacy boundaries,
  correlation-ID use, reviewer management, retention, rate limits, and secret
  rotation.
