# frontend-analysis-workflow Specification

## Purpose
TBD - created by archiving change cv-upload-results. Update Purpose after archive.
## Requirements
### Requirement: Authenticated multi-file upload panel
The `/analyze` page SHALL provide authenticated users with a multi-file upload interface supporting `.pdf` and `.docx` inputs via click-select and drag-drop.

#### Scenario: Queue multiple files
- **WHEN** a user selects or drops multiple supported files
- **THEN** the UI displays queued file names before submission

#### Scenario: Submission state
- **WHEN** analysis submission is in progress
- **THEN** the UI shows a loading state and prevents duplicate submissions

### Requirement: Session-protected web analysis proxy
The web app SHALL expose `POST /api/analyze` that verifies session and forwards multipart files to backend `POST /analyze/batch` using `INTERNAL_API_URL`.

#### Scenario: Unauthenticated proxy call
- **WHEN** an unauthenticated client calls `POST /api/analyze`
- **THEN** the route returns HTTP 401 and does not forward to backend

#### Scenario: Authenticated proxy forwarding
- **WHEN** an authenticated client submits files to `POST /api/analyze`
- **THEN** the route forwards all files to backend `/analyze/batch` and returns backend JSON response

### Requirement: Explainable per-file result rendering
The analyze UI SHALL render one card per file, including band, score, claimed location, summary, findings table, and disclaimer.

#### Scenario: Successful file result
- **WHEN** backend returns `status: ok` for a file
- **THEN** the UI shows band, score, claimed location, summary, and expandable findings (`signal`, `observed`, `claimed`, `direction`, `weight`, `rationale`)

#### Scenario: Failed file result
- **WHEN** backend returns `status: error` for a file
- **THEN** the UI shows the file-level error while preserving successful results for other files

### Requirement: Distinct gray-band treatment
The UI SHALL render gray (insufficient evidence) as a distinct neutral warning state, not a positive/pass state.

#### Scenario: Gray band card
- **WHEN** a report band is `gray`
- **THEN** the card style and badge clearly communicate insufficient evidence and route to human review

