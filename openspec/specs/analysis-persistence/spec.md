# analysis-persistence Specification

## Purpose
Defines how completed analyses are stored, listed, previewed, and deleted, and
how retention bounds their lifetime.

## Requirements

### Requirement: Owner-scoped analysis records
Every analysis SHALL be persisted in the API SQLite volume and scoped to the `X-Analysis-Access-Token` that created it. `GET /analyses` lists the caller's analyses, `GET /analyses/{id}` returns a stored report with capability flags attached, `GET /analyses/{id}/diagnostics` returns usage and cost diagnostics, `DELETE /analyses/{id}` and `DELETE /analyses` remove records. Records the caller does not own SHALL be indistinguishable from missing ones. Analysis data is transient and recruiter-owned. Deletion (`DELETE /analyses/{id}`, `DELETE /analyses`) and retention purge remove recruiter-owned analysis records (reports, runs, source documents, research cache, audit logs), but SHALL leave long-lived platform records (the AI usage ledger and contextual feedback data) intact.

#### Scenario: Foreign token
- **WHEN** a request presents a token that did not create the analysis
- **THEN** the API responds 404 `analysis_not_found`

### Requirement: Stored source documents
After a report is persisted successfully, the API SHALL store the original uploaded bytes together with the upload filename and a content type derived from the extension (`application/pdf` or the DOCX media type) in a `source_documents` row keyed by `analysis_id`. A storage failure SHALL be recorded as a diagnostic event and SHALL NOT fail the analysis. `GET /analyses` items SHALL carry `has_document` reflecting whether a stored copy exists. `GET /analyses/{id}/document` SHALL return the stored bytes with the stored `Content-Type`, `Content-Disposition: inline` (header-safe `filename` plus RFC 5987 `filename*` when the name is not plain ASCII) and `Cache-Control: private, no-store`, using the same `X-Analysis-Access-Token` ownership check as `GET /analyses/{id}`. Stored documents are deleted together with the analysis by `DELETE /analyses/{id}`, `DELETE /analyses`, and retention purge.

#### Scenario: Owner fetches stored document
- **WHEN** the owning token requests `/analyses/{id}/document` for an analysis whose upload was stored
- **THEN** the API responds 200 with the original bytes, content type, inline disposition and `private, no-store` caching

#### Scenario: Foreign token or missing copy
- **WHEN** the token did not create the analysis, or no stored copy exists
- **THEN** the API responds 404 `analysis_not_found`

#### Scenario: Storage failure
- **WHEN** storing the upload fails after the report was persisted
- **THEN** the analysis still succeeds, `has_document` is false, and a `persistence_failed` diagnostic event with `source_document_persistence_error` is recorded

### Requirement: Retention
`GET`/`PUT /settings/retention` SHALL expose the retention window in days, defaulting to `CV_VALIDATOR_RETENTION_DAYS` (90). Out-of-range values are rejected with 422 `retention_days_out_of_range`. Expired analyses, including their stored source documents, are purged when the list endpoint runs. Purging expired analyses SHALL NOT delete associated feedback data or AI usage ledger rows.

#### Scenario: Retention lowered
- **WHEN** retention is lowered below the age of stored analyses
- **THEN** those analyses and their stored documents disappear from the next list call

### Requirement: Recent analyses and document preview
The analyze screen SHALL list the caller's recent analyses and allow reopening one. When `has_document` is true, the web app SHALL fetch the stored copy through `/api/analyses/{id}/document` (a proxy that authenticates the web user and forwards the owner token) and preview the PDF or DOCX exactly as it does for a fresh upload, without re-uploading. Deleting from the UI SHALL call the corresponding API delete through the web proxy.

#### Scenario: Reopen recent analysis
- **WHEN** the user selects a recent analysis
- **THEN** the stored report renders with the same research and feedback state
