## Purpose

Defines privacy-safe owner-scoped feedback, safe failure diagnostics, reviewer
access, and internal triage for CV Analyzer output.

## ADDED Requirements

### Requirement: Stable server-issued targets
The system SHALL accept feedback only for a server-materialized target belonging
to a persisted owner-scoped analysis. Target kinds SHALL be `review_finding`,
`structured_fact`, `structural_observation`, `file_detail`, `link_result`,
`company_research_result`, `education_research_result`,
`linkedin_research_result`, `operation_failure`, and `report_overall`. A target
SHALL use opaque identity and code-owned source metadata; the client MUST NOT
create targets or use display text as identity.

#### Scenario: Owner loads a supported item
- **WHEN** an owner loads a persisted supported report item
- **THEN** the system returns the same stable target on repeated loads

#### Scenario: Client invents or mismatches a target
- **WHEN** a client submits an unknown target or one from another analysis
- **THEN** the system rejects the request without storing or disclosing feedback

#### Scenario: Legacy mapping is ambiguous
- **WHEN** a retained item cannot be mapped from safe structural identity
- **THEN** the system leaves it without a feedback target rather than guessing

### Requirement: Valid contextual feedback
An owner SHALL be able to submit `helpful`, `not_helpful`, or comment-only
feedback. A regular submission SHALL contain a normalized 12–180 character
comment or `not_helpful` with one closed reason: `inaccurate`,
`missing_context`, `misleading_importance`, `duplicate`, `unclear`,
`stale_research`, `wrong_source`, or `other`. Helpful and neutral feedback SHALL
require a valid comment. A failure target MAY omit the comment and SHALL use
`not_helpful` plus `operation_failed`. Feedback SHALL NOT change the report.

#### Scenario: Helpful has no comment
- **WHEN** the owner selects helpful without a valid comment
- **THEN** the system does not accept the submission

#### Scenario: Negative reason replaces prose
- **WHEN** the owner selects not helpful and one valid reason
- **THEN** the system accepts feedback without requiring a comment

#### Scenario: Neutral comment is valid
- **WHEN** the owner supplies a valid comment without selecting a rating
- **THEN** the system stores comment-only feedback for the target

### Requirement: One current response per actor and target
The system SHALL maintain at most one current response per authenticated actor
and target. Equivalent repeated submissions SHALL be idempotent. The owner SHALL
be able to update or withdraw the response while the analysis is retained.
Withdrawal SHALL remove comment and triage content while retaining only a
minimal comment-free tombstone.

#### Scenario: Submission is repeated
- **WHEN** the same actor repeats an equivalent request
- **THEN** the system returns the current response without creating a duplicate

#### Scenario: Feedback is withdrawn
- **WHEN** the actor withdraws feedback
- **THEN** active feedback and its comment no longer appear in report or inbox

### Requirement: Owner-scoped access
Feedback create, read, update, and withdrawal SHALL require the same owner
authorization as the analysis. Cross-owner and unauthenticated requests MUST NOT
reveal whether the analysis, target, or feedback exists.

#### Scenario: Another user guesses identifiers
- **WHEN** another user requests feedback using guessed identifiers
- **THEN** the system returns a non-disclosing authorization/not-found response

### Requirement: Minimized and sanitized storage
Feedback storage MUST NOT copy CV files/text, evidence, candidate facts, display
labels, prompts, model responses, research content, raw logs, exception text,
stack traces, request/response bodies, browser state, secrets, or complete report
payloads. It MAY store target references, closed classifications, sanitized
comment, technical versions, timestamps, pseudonymous actors, and the closed
failure envelope. Comments SHALL be normalized and detected emails, phone
numbers, and URLs SHALL be redacted or rejected without logging
the rejected raw text.

#### Scenario: Comment contains contact data
- **WHEN** a comment contains detected contact data or URL
- **THEN** the system does not persist that value verbatim

### Requirement: Safe operation-failure feedback
Persisted AI-analysis/retry and company/education/LinkedIn research failures MAY
receive an `operation_failure` target. Its context SHALL be generated server-side
from only operation kind, normalized error code, retryability, attempt count,
occurrence time, correlation ID, and approved technical versions. The client
MUST NOT attach or override diagnostic fields. Feedback MUST NOT invoke retry.

#### Scenario: Owner reports a persisted failure
- **WHEN** the owner submits feedback from a targeted failure state
- **THEN** the system stores `not_helpful` and `operation_failed` with only the
  server-owned diagnostic envelope

#### Scenario: Client submits purported logs
- **WHEN** the request includes raw logs or an unknown diagnostic field
- **THEN** the system rejects that diagnostic input and does not echo it

#### Scenario: Historical diagnostics are unavailable
- **WHEN** a stable failure target lacks a complete safe snapshot
- **THEN** the system records `diagnostics_unavailable` and does not fetch logs

### Requirement: DB-backed reviewer access
Inbox access SHALL require an active persisted `owner` or `reviewer` role tied to
an existing verified Better Auth user. Owners SHALL manage access by exact
verified email; reviewers SHALL NOT manage roles. The first owner SHALL be
created only by a server-side bootstrap command, and the last active owner SHALL
not be removable through the UI. Every protected route SHALL authorize on the
server regardless of sidebar visibility.

#### Scenario: Owner grants reviewer access
- **WHEN** an owner grants reviewer to an existing verified user
- **THEN** that user can open the inbox after the next authorization check

#### Scenario: Reviewer tries to grant access
- **WHEN** a reviewer requests an access mutation
- **THEN** the system returns HTTP 403 and changes no role

#### Scenario: Reviewer access is revoked
- **WHEN** an owner revokes a reviewer
- **THEN** subsequent inbox, aggregate, and triage requests are denied

### Requirement: Internal feedback inbox
The inbox SHALL provide cursor pagination, counts, closed filters for rating,
reason, target kind/source/version, triage status, and date, plus triage states
`new`, `reviewing`, `planned`, `resolved`, and `wont_fix`. It SHALL expose only
safe target, feedback, version, failure, and pseudonymous triage metadata. It
MUST NOT join candidate report/audit payloads or export raw data.

#### Scenario: Reviewer investigates a recurring failure
- **WHEN** a reviewer filters by operation, error code, and version
- **THEN** matching entries and counts appear without CV content or raw logs

### Requirement: Feedback follows analysis retention and has no authority
Targets, responses, events, triage, and failure context SHALL be deleted with
manual analysis deletion or retention expiry. Feedback MUST NOT mutate or hide
facts, findings, evidence, research, score, band, prompt, cache, or report, and
MUST NOT trigger AI, research, retry, hiring action, or automated remediation.

#### Scenario: Analysis is purged
- **WHEN** a retained analysis is deleted or expires
- **THEN** its complete feedback graph is removed in the same lifecycle

#### Scenario: Finding is reported inaccurate
- **WHEN** feedback marks a finding inaccurate
- **THEN** the finding and all decision-support output remain unchanged

### Requirement: VPS deployment preserves feedback data
Feedback schema initialization SHALL be additive and idempotent. Production
replacement deploys after merge to `main` SHALL reuse the existing
`cv_validator_data` and `web_auth_data` volumes. Deployment and rollback MUST NOT
remove, recreate, or rename those volumes. Owner bootstrap SHALL be a one-time
operator action, not an autodeploy step.

#### Scenario: Main is autodeployed
- **WHEN** replacement containers start after merge to `main`
- **THEN** feedback and access schema are available on the existing volumes
- **AND** existing auth, analyses, and feedback remain available

#### Scenario: Release is rolled back
- **WHEN** feedback is disabled or the previous reviewed release is restored
- **THEN** additive feedback data remains intact for a later compatible release
