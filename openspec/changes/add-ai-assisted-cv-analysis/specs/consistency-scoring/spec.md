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

### Requirement: Requested location signals
The report SHALL extract the phone country and stated city or address. It SHALL check whether the locality exists and identify its country when reference data allows it. It SHALL show flags for a phone country outside the EU, an atypical or small stated locality outside the EU, and a combined `location_outside_eu` signal based on phone and stated-location evidence.

#### Scenario: Phone prefix points outside the EU
- **WHEN** a parsed phone number maps to a non-EU country
- **THEN** the report shows the requested phone-country flag and the parsed country evidence

#### Scenario: Stated locality can be resolved
- **WHEN** the system resolves the stated city or address to a country
- **THEN** the report shows the resolved location and whether the requested non-EU or atypical-locality flag applies

#### Scenario: Stated locality cannot be resolved
- **WHEN** the system cannot confirm that the stated locality exists
- **THEN** the report shows a location-validation flag with the attempted value and does not guess its country

#### Scenario: Location signals are combined
- **WHEN** phone and stated-location signals are available
- **THEN** the report includes a combined location flag with both observations and a disclaimer that they do not prove physical location
