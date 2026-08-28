## ADDED Requirements

### Requirement: Prefer code-owned structured records with legacy fallback

For a report containing valid `document-understanding-v1`, the analysis UI SHALL render code-owned education, employment, and skill records first and MAY append independently validated AI-only additions without overwriting code fields. It SHALL use explicit timeline-to-record links for new reports and MUST NOT associate records solely by displayed date text. For a legacy report whose understanding value is `null`, the UI SHALL preserve the existing validated AI-fact rendering and date-based compatibility behavior.

Company and education research controls SHALL use the derived authorized request subjects. Document-AI failure SHALL not hide a control backed by a code-owned subject when public research remains enabled. The user/deployment AI-disabled state SHALL continue to disable all AI-backed company, education, and LinkedIn research controls.

#### Scenario: New report has code-owned records
- **WHEN** valid V1 understanding contains education, employment, or skills
- **THEN** the UI renders those code-owned values with their confidence and unknown-field states independently of the document-AI outcome

#### Scenario: Two records share displayed dates
- **WHEN** two records have identical displayed date ranges
- **THEN** explicit stable links attach the correct timeline and entity details

#### Scenario: Legacy report is opened
- **WHEN** `document_understanding` is null and validated legacy AI facts exist
- **THEN** the existing AI-derived overview remains available without pretending it is code-owned

#### Scenario: User disables AI
- **WHEN** the overall AI/public-research switch is disabled
- **THEN** company, education, and LinkedIn research controls remain disabled even if code-owned public subjects exist
