## ADDED Requirements

### Requirement: Collapsed file-detail disclosure
The completed CV report SHALL provide a collapsed `File details` disclosure containing available standard metadata. The disclosure SHALL distinguish missing values from extracted values and SHALL NOT present metadata as proof of authenticity, fraud, or candidate behavior.

#### Scenario: Recruiter opens file details
- **WHEN** a completed report contains file-detail data and the recruiter opens the disclosure
- **THEN** the UI shows compact labels and values for available metadata without a suspicious badge

### Requirement: Compact suspicious link flags
The recruiter-facing checklist SHALL show each suspicious link anomaly as a compact `SUSPICIOUS` flag attached to the affected declaration. The collapsed row SHALL contain a short code-owned title; disclosure SHALL show the displayed value, sanitized target, outcome, reason code, source location, and available check evidence. It MUST NOT show a candidate-level fraud or lying verdict.

#### Scenario: Declared portfolio returns not found
- **WHEN** the report contains `declared_link_not_found` for a portfolio link
- **THEN** the visible row shows `SUSPICIOUS` and a short not-found title
- **AND** the disclosure shows the sanitized URL and terminal status

### Requirement: Neutral unavailable link results
The UI SHALL keep inconclusive link checks available under a neutral `UNAVAILABLE` state and MUST NOT count or style them as suspicious.

#### Scenario: Link check is blocked
- **WHEN** a report link check is unavailable because of HTTP `403`, HTTP `429`, anti-bot behavior, or a network limit
- **THEN** the UI shows a neutral unavailable result with a retry-independent explanation

## MODIFIED Requirements

### Requirement: Explainable per-file result rendering
The analyze UI SHALL render one card per file, including structured CV facts, a concise summary, the complete finding checklist, available research, file details, link-inspection outcomes, evidence, and the decision-support disclaimer. It MUST NOT present the deprecated location score or band as the overall assessment of the CV or candidate.

#### Scenario: Successful file result
- **WHEN** backend returns `status: ok` for a file
- **THEN** the UI shows structured facts, summary, compact findings, available research, file/link inspection, expandable evidence, and the decision-support disclaimer
- **AND** does not lead with or require a numeric score or color band

#### Scenario: Failed file result
- **WHEN** backend returns `status: error` for a file
- **THEN** the UI shows the file-level error while preserving successful results for other files

### Requirement: Compact finding hierarchy
The UI SHALL retain separate `Needs attention` and `Worth knowing` groups, plus collapsed remaining signals, without hiding ordinary finding explanations behind mandatory extra clicks. Counts MAY remain as compact inline metadata but MUST NOT consume a separate dashboard-metric row. Deprecated deterministic score/band output SHALL NOT be presented as the overall CV or candidate assessment.

#### Scenario: Report contains findings
- **WHEN** one CV report is rendered
- **THEN** visible findings show their title, explanation, authority, confidence, and first evidence without opening another surface

## REMOVED Requirements

### Requirement: Distinct gray-band treatment
**Reason**: The location-only deterministic score and bands are deprecated legacy output and no longer represent the recruiter-facing assessment of the CV.

**Migration**: Existing API and persisted score/band fields remain readable during the compatibility period, while the UI uses concrete findings and neutral unavailable states instead of a gray-band card.
