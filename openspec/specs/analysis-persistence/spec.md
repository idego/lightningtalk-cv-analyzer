# analysis-persistence Specification

## Purpose
Defines how completed analyses are stored, listed, previewed, and deleted, and
how retention bounds their lifetime.

## Requirements

### Requirement: Owner-scoped analysis records
Every analysis SHALL be persisted in the API SQLite volume with the authenticated Better Auth user id as its stable `owner_user_id`. The browser MUST NOT receive an analysis-owner capability token; the authenticated Next.js proxy forwards the server-derived owner id to the private API. `GET /analyses` lists the caller's analyses, `GET /analyses/{id}` returns a stored report with capability flags attached, `GET /analyses/{id}/diagnostics` returns usage and cost diagnostics, `DELETE /analyses/{id}` and `DELETE /analyses` remove records. Records the caller does not own SHALL be indistinguishable from missing ones. Analysis data is transient and recruiter-owned. Deletion (`DELETE /analyses/{id}`, `DELETE /analyses`) and retention purge remove recruiter-owned analysis records (reports, runs, source documents, per-analysis research and cache-audit rows, audit logs), but SHALL leave long-lived platform records (the AI usage ledger and contextual feedback data) intact.

#### Scenario: Foreign owner
- **WHEN** an authenticated user id does not own the analysis
- **THEN** the API responds 404 `analysis_not_found`

### Requirement: Analysis groups
Every persisted analysis SHALL belong to exactly one owner-scoped analysis group. Named groups (for example one job offer) live in an `analysis_groups` table keyed by `group_id` and `owner_user_id`; `reports.group_id` is nullable and a NULL value means the analysis belongs to the synthetic `unassigned` group, which always exists, is listed last, and cannot be created or removed. `GET /analysis-groups` returns the caller's groups oldest first, each with its analyses newest first, followed by `unassigned`. `POST /analysis-groups` creates a named group (whitespace-normalized, 1-120 characters, otherwise 400 `invalid_group_name`); names are unique per owner ignoring case, and a duplicate is rejected with 409 `analysis_group_name_taken`. `DELETE /analysis-groups/{id}` deletes the group together with every analysis in it using the same deletion semantics as `DELETE /analyses/{id}`; `DELETE /analysis-groups/unassigned` deletes only the caller's ungrouped analyses and keeps the `unassigned` group. `POST /analyze` accepts an optional `X-Analysis-Group-Id` header; a value of `unassigned` or an absent header stores the analysis ungrouped, and a group id the caller does not own is rejected with 404 `analysis_group_not_found`. `PUT /analyses/{id}/group` with `{"group_id": <id or "unassigned" or null>}` moves one owned analysis into another owned group (404 `analysis_not_found` or `analysis_group_not_found` otherwise). Existing databases gain the `group_id` column additively and their analyses appear under `unassigned`.

#### Scenario: Batch assigned to an offer group
- **WHEN** the owner uploads a batch with `X-Analysis-Group-Id` set to one of their groups
- **THEN** each resulting analysis is listed under that group and not under `unassigned`

#### Scenario: Duplicate group name
- **WHEN** the owner creates a group named `junior BACKEND` while already owning `Junior backend`
- **THEN** the API responds 409 `analysis_group_name_taken` and the UI shows that a group with this name already exists

#### Scenario: Foreign group
- **WHEN** the caller supplies a group id owned by another user
- **THEN** the API responds 404 `analysis_group_not_found` and no analysis is stored

#### Scenario: Move analysis to another group
- **WHEN** the owner moves an analysis from `unassigned` into one of their groups
- **THEN** the analysis is listed under that group and no longer under `unassigned`, without changing the stored report

#### Scenario: Delete group
- **WHEN** the owner deletes a named group
- **THEN** the group and all of its analyses, stored documents and share capabilities are removed, while feedback and AI usage ledger rows remain

### Requirement: Stored source documents
After a report is persisted successfully, the API SHALL store the original uploaded bytes together with the upload filename and a content type derived from the extension (`application/pdf` or the DOCX media type) in a `source_documents` row keyed by `analysis_id`. A storage failure SHALL be recorded as a diagnostic event and SHALL NOT fail the analysis. `GET /analyses` items SHALL carry `has_document` reflecting whether a stored copy exists. `GET /analyses/{id}/document` SHALL return the stored bytes with the stored `Content-Type`, `Content-Disposition: inline` (header-safe `filename` plus RFC 5987 `filename*` when the name is not plain ASCII) and `Cache-Control: private, no-store`, using the same server-derived owner-id check as `GET /analyses/{id}`. Stored documents are deleted together with the analysis by `DELETE /analyses/{id}`, `DELETE /analyses`, and retention purge.

#### Scenario: Owner fetches stored document
- **WHEN** the owning authenticated user requests `/analyses/{id}/document` for an analysis whose upload was stored
- **THEN** the API responds 200 with the original bytes, content type, inline disposition and `private, no-store` caching

#### Scenario: Foreign owner or missing copy
- **WHEN** the authenticated user does not own the analysis, or no stored copy exists
- **THEN** the API responds 404 `analysis_not_found`

#### Scenario: Storage failure
- **WHEN** storing the upload fails after the report was persisted
- **THEN** the analysis still succeeds, `has_document` is false, and a `persistence_failed` diagnostic event with `source_document_persistence_error` is recorded

### Requirement: Retention
`GET /settings/retention` SHALL expose the deployment-wide retention window in days, defaulting to `CV_VALIDATOR_RETENTION_DAYS` (90). The authenticated web boundary SHALL allow `PUT /settings/retention` only to an active feedback `owner`; the private API SHALL additionally require the web-to-API internal admin secret for that write. The Settings UI SHALL explicitly confirm that the change affects every user's stored analyses. Out-of-range values are rejected with 422 `retention_days_out_of_range`. Expiration is determined by report age (or run age only for report-less runs); purge runs on API startup and lifecycle/list writes. Purging expired analyses SHALL NOT delete associated feedback data or AI usage ledger rows.

#### Scenario: Retention lowered
- **WHEN** retention is lowered below the age of stored analyses
- **THEN** those analyses and their stored documents disappear from the next list call

### Requirement: Recent analyses and document preview
The analyze screen SHALL list the caller's recent analyses and allow reopening one. When `has_document` is true, the web app SHALL fetch the stored copy through `/api/analyses/{id}/document` (a proxy that authenticates the web user and forwards the server-derived owner id) and preview the PDF or DOCX exactly as it does for a fresh upload, without re-uploading. Deleting from the UI SHALL call the corresponding API delete through the web proxy; the Recent analyses module itself offers no delete control, deletion happens on the Analyses page.

#### Scenario: Reopen recent analysis
- **WHEN** the user selects a recent analysis
- **THEN** the stored report renders with the same research and feedback state

### Requirement: Scoped read-only analysis sharing
An analysis owner SHALL be able to create a high-entropy share capability for one persisted analysis. The API SHALL store only a hash of that capability and SHALL accept it only on read-only shared-report and shared-document endpoints for the same analysis. A share capability MUST NOT grant owner history, delete, feedback, research, diagnostics, usage, or retention access, and MUST NOT be accepted as an owner identity. Deleting or retention-purging the analysis SHALL invalidate all of its share capabilities. The web app SHALL require its normal authenticated session before proxying shared report or document reads.

#### Scenario: Authenticated colleague opens a shared analysis
- **WHEN** the owner creates a share link and another authenticated web user opens it with the valid per-analysis share capability
- **THEN** that user can read the persisted report and stored document in a read-only report view without gaining access to the owner's other analyses or mutation endpoints

#### Scenario: Shared analysis is deleted
- **WHEN** the owning user deletes an analysis that has active share capabilities
- **THEN** those shared report and document URLs stop resolving


### Requirement: Preserve existing v2 owners on upgrade
An upgrade from token-owned `base-analysis-v2` SHALL retain legacy owner hashes in
a transient mapping until matched to an authenticated user through the private
web/API boundary. The API SHALL derive the prior HMAC from a server-held secret,
not accept a browser-supplied claim. Binding SHALL be idempotent, preserve source
documents and shares, and re-key feedback authorship together with its triage and
events without losing snapshots. New writes SHALL use stable user ids. Unmatched
mappings SHALL expire with their analysis, not delete long-lived feedback.

#### Scenario: Existing owner returns after deployment
- **WHEN** the authenticated owner opens history after the web/API upgrade
- **THEN** matching retained reports and uploads are available without re-upload
- **AND** another user's reports remain inaccessible
- **AND** prior feedback and triage are preserved
