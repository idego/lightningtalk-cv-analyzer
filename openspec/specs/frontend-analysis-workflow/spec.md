# frontend-analysis-workflow Specification

## Purpose
Defines the authenticated recruiter workflow for uploading CVs, reviewing
deterministic and AI-assisted findings, starting optional research, and
navigating persisted analysis results.

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

### Requirement: Synchronous AI-assisted analysis experience
The analyze UI SHALL keep the current upload flow. After submission it SHALL
replace the upload controls and queued-file list with real per-file progress,
submit accepted CVs one at a time, and render each result as it completes. The
loading state SHALL identify the current file, completed count, failures, and
elapsed time without presenting an invented percentage or completion estimate.

#### Scenario: Single CV analysis completes
- **WHEN** the API returns the AI-assisted report
- **THEN** the UI replaces the loading state with that report

#### Scenario: Batch contains file errors
- **WHEN** the batch response contains successful reports and failed files
- **THEN** the UI shows each returned report and each isolated error

#### Scenario: Multi-file analysis is running
- **WHEN** four CVs were submitted and the second is being analyzed
- **THEN** the UI shows `Analyzing 2 of 4`, the current filename, and completed or failed status for earlier files

### Requirement: Finding hierarchy
The UI SHALL group findings as `requires attention`, `worth knowing`, and `remaining signals`. It SHALL collapse `remaining signals` by default but keep all findings available.

#### Scenario: Low-importance findings exist
- **WHEN** a report has low-importance findings
- **THEN** the UI keeps them in the collapsed `remaining signals` section

### Requirement: Complete candidate flag checklist
The UI SHALL show a per-candidate checklist containing every detected location, LinkedIn, company, education, deterministic, and AI-assisted flag with a short reason. It SHALL merge duplicate serialized finding and observation representations into one recruiter-facing item. Repeated outside-EU facts SHALL be summarized in one item with supporting details available on disclosure, and several possible LinkedIn profiles SHALL produce one summary item plus separate profile cards.

#### Scenario: Candidate has findings from several sources
- **WHEN** document analysis, fixed rules, or research return flags
- **THEN** the report lists all flags and identifies their source and reason

#### Scenario: One deterministic signal is serialized twice
- **WHEN** one code-owned signal is available both as a scored finding and its source observation
- **THEN** the recruiter-facing checklist shows it once

#### Scenario: Several facts point outside the EU
- **WHEN** stated location, phone, or education facts all point outside the EU
- **THEN** the visible checklist summarizes the shared conclusion once and keeps the distinct supporting facts available

### Requirement: Readable HTML report
The UI SHALL render each candidate result as a readable HTML report backed by the same report data returned by the API.

#### Scenario: Candidate report is ready
- **WHEN** the recruiter opens a completed analysis
- **THEN** the UI shows structured facts, the flag checklist, evidence, and available research results

### Requirement: Structured CV overview
The CV overview SHALL group contact, location, education, and experience facts with compact icons and accessible labels. Phone country SHALL appear as secondary information under the phone number. Education and experience SHALL show deterministic minimum-to-maximum date summaries and summed non-overlapping duration when parseable, without an AI call.

#### Scenario: Structured facts are available
- **WHEN** the report contains contact, location, education, or employment facts
- **THEN** the overview groups them by subject and uses compact secondary text instead of a flat text wall

#### Scenario: Date ranges are parseable
- **WHEN** education or experience entries contain supported date ranges
- **THEN** code displays their earliest-to-latest span and summed duration without changing report facts or invoking AI

### Requirement: Honest disclosure controls
Cards with hidden details SHALL allow the recruiter to open them by clicking the whole card, and MAY preview on hover when the browser supports hover and the setting is enabled. A card with no hidden content SHALL show no chevron and SHALL NOT act as expandable. LinkedIn possible profiles SHALL each be separate disclosure cards with a clearly styled external `Open profile` action.

#### Scenario: Research section has no completed details
- **WHEN** a research section contains only its title and start action
- **THEN** it shows no expansion affordance

#### Scenario: Collapsed report card contains details
- **WHEN** a recruiter clicks anywhere on the non-interactive area of that card
- **THEN** the card opens without requiring a precise click on its title

### Requirement: Result navigation
The completed-result view SHALL provide a left-aligned `Back` action with a back arrow that returns to the upload flow.

#### Scenario: Recruiter wants another analysis
- **WHEN** the recruiter activates `Back`
- **THEN** the current results are cleared and the upload flow is shown

### Requirement: Synchronized original-document preview
The UI SHALL keep each submitted file in browser memory for the lifetime of the
result view and provide a hideable original-document preview beside the report.
The preview width SHALL be resizable. Report and preview SHALL scroll
independently. With several results, the preview SHALL follow the report that is
currently dominant in the report viewport. Preview state MUST NOT upload the
file to any additional service or persist the original file.

#### Scenario: Recruiter reviews several CVs
- **WHEN** scrolling makes another candidate report the active visible report
- **THEN** the preview switches to the corresponding original file

#### Scenario: Preview is not needed
- **WHEN** the recruiter hides the preview
- **THEN** the report uses the available width and a visible control can restore the preview

### Requirement: Compact finding hierarchy
The UI SHALL retain separate `Needs attention` and `Worth knowing` groups, plus
collapsed remaining signals, without hiding ordinary finding explanations
behind mandatory extra clicks. Counts MAY remain as compact inline metadata but
MUST NOT consume a separate dashboard-metric row. Deterministic gray assessment
SHALL remain secondary rather than presenting the AI-assisted report as empty.

#### Scenario: Report contains findings
- **WHEN** one candidate report is rendered
- **THEN** visible findings show their title, explanation, authority, confidence, and first evidence without opening another surface

### Requirement: Settings and readiness surface
The sidebar SHALL contain a Settings destination. Settings SHALL independently
configure UI language and AI report language and SHALL show a health check for
all required analyzer capabilities. English SHALL be the default UI language.
Settings MAY be stored in the browser for V1.

#### Scenario: Capability is unavailable
- **WHEN** Settings loads and health reports a missing required capability
- **THEN** the affected check is visibly marked unavailable with a recovery hint
- **AND** the overall status is not shown as ready

### Requirement: Partial AI validation warning
The UI SHALL show a neutral partial-validation warning alongside valid AI facts
and findings when the base report contains `validation_warnings`. It SHALL NOT
hide accepted output or turn the warning into a score, band, rejection, or
verification claim.

#### Scenario: Some AI fields are unsupported
- **WHEN** the API returns valid facts/findings together with the partial
  validation warning
- **THEN** the UI shows the valid output and the Polish warning
  `Część danych nie została pokazana, ponieważ nie udało się potwierdzić ich w
  tekście CV.`

### Requirement: User-controlled research actions
The UI SHALL provide separate actions for company, education/certification, and LinkedIn research after the base report is ready. It SHALL show a request-level loading state and keep other report content visible.

#### Scenario: User starts one research category
- **WHEN** the user starts one category
- **THEN** only that action becomes busy
- **AND** the base report and other completed categories remain visible

#### Scenario: Research succeeds
- **WHEN** the API returns a completed category result
- **THEN** the UI adds or replaces that category without a full page reload

#### Scenario: Research fails
- **WHEN** the request returns an error
- **THEN** the UI shows the category error, keeps the report, and lets the user retry

### Requirement: Plain-language reviewer report
The report SHALL use a project house style informed by global-audience and accessibility guidance and ASD-STE100 principles without claiming full ASD-STE100 compliance. Known finding categories SHALL prefer concise code-owned text with `What we found`, `Why it matters`, and `What to check`. Internal category, importance, and confidence labels MUST NOT be the primary reviewer explanation.

#### Scenario: Known finding category is displayed
- **WHEN** the report renders a known category such as a timeline overlap
- **THEN** it leads with a short plain-language result and a concrete reviewer check

### Requirement: Automatic research settings
Settings SHALL provide a master automatic-public-research control and independent company, education, and LinkedIn discovery controls. Upload SHALL name enabled automatic categories. After a base report succeeds, the UI SHALL start enabled categories with bounded concurrency and independent status. Research failure MUST NOT remove the base report. LinkedIn discovery SHALL expose possible profiles as manual-review links and MUST NOT offer profile confirmation or automated profile-to-CV comparison.

#### Scenario: Automatic research is enabled
- **WHEN** a base report completes with one or more automatic categories enabled
- **THEN** enabled research actions start within the bounded client queue and update independently

### Requirement: Manual AI retry
When AI analysis is unavailable after bounded attempts, the UI SHALL retain the deterministic report, show a non-technical unavailable state, and provide a manual Retry action for that file.

#### Scenario: AI attempts are exhausted
- **WHEN** AI analysis remains unavailable after its bounded attempts
- **THEN** the deterministic report stays visible and the recruiter can retry AI analysis manually
