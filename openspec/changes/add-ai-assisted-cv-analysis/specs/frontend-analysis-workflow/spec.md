## ADDED Requirements

### Requirement: Progressive base-report experience
The analyze UI SHALL track each file on its own. It SHALL show a file's base report when document analysis completes and SHALL NOT wait for optional research.

#### Scenario: Batch files complete at different times
- **WHEN** one base report completes before the others
- **THEN** the UI shows that report and keeps pending states for other files

#### Scenario: Analysis state changes
- **WHEN** a file is `pending` or `running`
- **THEN** the UI refreshes its state until it becomes terminal

### Requirement: Finding hierarchy
The UI SHALL group findings as `requires attention`, `worth knowing`, and `remaining signals`. It SHALL collapse `remaining signals` by default but keep all findings available.

#### Scenario: Low-importance findings exist
- **WHEN** a report has low-importance findings
- **THEN** the UI keeps them in the collapsed `remaining signals` section

### Requirement: User-controlled research actions
The UI SHALL provide separate actions for company, education/certification, and LinkedIn research after the base report is ready.

#### Scenario: User selects one research category
- **WHEN** the user starts one category
- **THEN** only that category enters `pending` or `running`
- **AND** other categories remain inactive and available

### Requirement: Progressive research presentation
The UI SHALL show each research state and add completed results without a page reload.

#### Scenario: One research category fails
- **WHEN** one category becomes `failed`
- **THEN** the UI shows that failure and keeps the base report and other research results

#### Scenario: Research lacks evidence
- **WHEN** one category becomes `insufficient_evidence`
- **THEN** the UI shows a neutral message, not a negative candidate signal
