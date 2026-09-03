# analysis-persistence Specification

## Purpose
Defines how completed analyses are stored, listed, previewed, and deleted, and
how retention bounds their lifetime.

## Requirements

### Requirement: Owner-scoped analysis records
Every analysis SHALL be persisted in the API SQLite volume and scoped to the `X-Analysis-Access-Token` that created it. `GET /analyses` lists the caller's analyses, `GET /analyses/{id}` returns a stored report with capability flags attached, `GET /analyses/{id}/diagnostics` returns usage and cost diagnostics, `DELETE /analyses/{id}` and `DELETE /analyses` remove records. Records the caller does not own SHALL be indistinguishable from missing ones.

#### Scenario: Foreign token
- **WHEN** a request presents a token that did not create the analysis
- **THEN** the API responds 404 `analysis_not_found`

### Requirement: Retention
`GET`/`PUT /settings/retention` SHALL expose the retention window in days, defaulting to `CV_VALIDATOR_RETENTION_DAYS` (90). Out-of-range values are rejected with 422 `retention_days_out_of_range`. Expired analyses are purged when the list endpoint runs.

#### Scenario: Retention lowered
- **WHEN** retention is lowered below the age of stored analyses
- **THEN** those analyses disappear from the next list call

### Requirement: Recent analyses and document preview
The analyze screen SHALL list the caller's recent analyses and allow reopening one. A stored PDF or DOCX SHALL be previewable in the browser without re-uploading. Deleting from the UI SHALL call the corresponding API delete through the web proxy.

#### Scenario: Reopen recent analysis
- **WHEN** the user selects a recent analysis
- **THEN** the stored report renders with the same research and feedback state
