# contextual-feedback Specification

## Purpose
Defines decision-neutral reviewer feedback on analysis and research signals,
the maintainer inbox that triages it, and the owner/reviewer access model.
Feedback never changes a report, analysis output, research result, retry
state, or hiring action.

## Requirements

### Requirement: Feedback targets
Every visible signal in a report SHALL be addressable by a deterministic target id derived from the analysis id and the signal's kind and key. Supported kinds are `review_finding`, `structured_fact`, `structural_observation`, `file_detail`, `link_result`, `company_research_result`, `education_research_result`, `linkedin_research_result`, `operation_failure`, and `report_overall`.

Report controls SHALL expose feedback at the CV overview and whole-section level for worth-knowing findings, company research, education research, LinkedIn profile research, and remaining signals. Research entries and individual findings SHALL NOT render separate feedback controls.

#### Scenario: Same signal, same target
- **WHEN** the same analysis renders the same finding twice
- **THEN** both renderings resolve to the same target id

### Requirement: Contextual feedback capture
A signed-in user who can open an analysis SHALL be able to submit a comment without a rating, rate any target `helpful` or `not_helpful` without a comment, and optionally choose one reason (`inaccurate`, `missing_context`, `misleading_importance`, `duplicate`, `unclear`, `stale_research`, `wrong_source`, `operation_failed`, `other`). At least a rating or a non-empty comment is required. The response SHALL retain the author's email and a snapshot of the displayed section (`context_label` up to 200 characters, `context_text` up to 12000 characters) so maintainers can review it in context. A comment SHALL be at most 180 characters after whitespace normalization and MUST NOT contain URLs, email addresses, or phone numbers. Writes use `PUT /analyses/{analysis_id}/feedback/{target_id}` through the web proxy, which caps a request body at 16 KiB. One actor may write at most 30 times per minute per analysis.

#### Scenario: Comment with contact data
- **WHEN** a comment contains an email address, URL, or phone-like number
- **THEN** the API rejects the write with a validation error

#### Scenario: Collection disabled
- **WHEN** an owner has disabled collection of new feedback
- **THEN** capture controls are hidden and the web proxy refuses new writes with 404 `feedback_disabled`, while existing feedback and the inbox stay available

#### Scenario: Rate limit exceeded
- **WHEN** an actor exceeds 30 feedback writes in a minute
- **THEN** the API responds 422 `feedback_rate_limit`

### Requirement: Feedback lifecycle and analysis decoupling
Analysis data is transient and recruiter-owned. Feedback is long-lived platform and review data that survives analysis deletion and retention purge, similar to the AI usage ledger. When an analysis is deleted through single deletion (`DELETE /analyses/{id}`), bulk deletion (`DELETE /analyses`), or automated retention purge, all associated feedback targets, responses, triage notes, displayed context snapshots, and diagnostic context SHALL remain intact. The `analysis_id` SHALL be retained as a historical correlation identifier without a foreign key cascade to `reports`.

#### Scenario: Single analysis deletion preserves feedback
- **WHEN** an analysis is deleted by an authorized recruiter
- **THEN** its associated feedback targets, responses, comments, and triage notes remain queryable in the maintainer inbox

#### Scenario: Retention purge preserves feedback
- **WHEN** expired analysis reports are removed by automated retention purge
- **THEN** all associated feedback data and displayed context snapshots remain preserved

### Requirement: Maintainer inbox and triage
Users holding an active `owner` or `reviewer` role SHALL see the `/feedback` inbox listing responses with filters for rating, reason, kind, triage status, source, version, operation, error code, and date range. They SHALL be able to set a triage status (`new`, `reviewing`, `planned`, `resolved`, `wont_fix`) with a team note of up to 500 characters (2 KiB request cap, same contact-data rule as comments) and delete a response. The API SHALL record the acting maintainer from the `X-Feedback-Maintainer` header that only the web proxy sets. The inbox MUST NOT store the uploaded original, raw model output, raw exceptions, request bodies, or logs.

#### Scenario: Triage without maintainer identity
- **WHEN** a triage request reaches the API without `X-Feedback-Maintainer`
- **THEN** the API responds 400 `maintainer_required`

#### Scenario: Retained context shown
- **WHEN** a maintainer opens a response in the inbox
- **THEN** the retained context label and snapshot are displayed alongside the comment

### Requirement: Owner and reviewer access
Feedback roles SHALL live in the web auth database table `feedback_access_by_email`, keyed by lower-cased email. Only owners may grant or revoke `owner`/`reviewer` roles on the Feedback access page, and only for emails in `ALLOWED_EMAIL_DOMAINS`. Access applies when that address signs in. The last active owner MUST NOT be demoted or revoked. Owners also toggle collection of new feedback from the same page.

#### Scenario: Last owner protected
- **WHEN** an owner tries to revoke or demote the only active owner
- **THEN** the change is refused with `last_owner_protected`

### Requirement: Access bootstrap
The one-shot `feedback-init` Compose service SHALL create the access tables and seed the owners listed in `config/feedback-access.json` only when the access table is empty. It MUST NOT restore access later changed in the UI. When `LOCAL_DEV_AUTH_BYPASS=true`, it SHALL also upsert `local-dev@localhost` as an active owner on every run. `web` starts only after `feedback-init` completes successfully.

#### Scenario: Config has no valid owner
- **WHEN** the config lists no owner email
- **THEN** `feedback-init` fails and `web` does not start

#### Scenario: Redeploy after UI changes
- **WHEN** the stack is redeployed with a non-empty access table
- **THEN** existing roles and revocations are preserved unchanged
