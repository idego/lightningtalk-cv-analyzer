## MODIFIED Requirements

### Requirement: Explainable, reproducible report
The report SHALL contain the deterministic score, band, and rule findings. It SHALL also contain available AI document findings, research findings, a summary, evidence, and the settings that produced each section. The same input and ruleset MUST produce the same deterministic score, band, and rule findings. The system SHALL make AI sections auditable through stored model, prompt, schema, and evidence data.

#### Scenario: Itemized findings
- **WHEN** the system produces a report
- **THEN** each deterministic signal shows its observed value, claimed value, direction, weight, and reason

#### Scenario: Itemized AI-assisted findings
- **WHEN** AI document or research findings are available
- **THEN** each finding shows its category, importance, confidence, reason, evidence, source location or URL, and configuration version

#### Scenario: Deterministic output
- **WHEN** the system analyzes the same CV twice with the same ruleset
- **THEN** both runs produce the same deterministic score, band, and rule findings

## ADDED Requirements

### Requirement: AI findings excluded from deterministic verdict
AI document and research findings MUST NOT change score weights or the four-band result.

#### Scenario: AI reports a high-importance inconsistency
- **WHEN** AI marks a finding as high importance
- **THEN** the system shows it for human review
- **AND** calculates score and band only from fixed rule signals
