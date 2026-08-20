## MODIFIED Requirements

### Requirement: Config-driven weighted scoring
The system SHALL compute a 0-100 consistency score from versioned, code-owned location facts and fixed rules. Weights SHALL be read from configuration and not hard-coded. AI-derived facts, associations, interpretations, and findings MUST NOT become weighted inputs.

#### Scenario: Signals agree with claim
- **WHEN** enough code-owned facts are consistent with the code-owned claimed location
- **THEN** the system produces a high score reflecting that deterministic agreement

#### Scenario: Strong signal conflicts with claim
- **WHEN** a strong code-owned fact such as an explicit international phone country conflicts with the code-owned claimed location
- **THEN** the conflict lowers the score by its configured weight

#### Scenario: Only AI interpretation resolves an ambiguity
- **WHEN** code-owned facts are insufficient but AI returns a plausible interpretation
- **THEN** the system keeps the deterministic result gray or otherwise insufficient and does not use the AI value as a weighted input

#### Scenario: Weights changed via configuration
- **WHEN** deterministic signal weights are updated in configuration
- **THEN** scoring reflects the new weights without code changes

### Requirement: Explainable, reproducible report
The report SHALL contain the deterministic score, band, code-owned facts and rule findings. It SHALL also contain available AI document findings, research findings, a summary, evidence, authority/source labels, and the settings that produced each section. The same input, deterministic extractor version, reference-data version, and ruleset MUST produce the same deterministic score, band, facts, and rule findings. The system SHALL make AI sections auditable through stored model, prompt, schema, deterministic-observation, and evidence data.

#### Scenario: Itemized findings
- **WHEN** the system produces a report
- **THEN** each deterministic finding shows its observed value, claimed value, direction, weight, reason, source evidence, and extractor version

#### Scenario: Itemized AI-assisted findings
- **WHEN** AI document or research findings are available
- **THEN** each finding shows its category, importance, confidence, reason, evidence, source location or URL, authority, and configuration version

#### Scenario: Deterministic output
- **WHEN** the system analyzes the same CV twice with the same deterministic extractor, reference data, and ruleset versions
- **THEN** both runs produce the same deterministic score, band, facts, and rule findings regardless of AI output

## ADDED Requirements

### Requirement: AI findings excluded from deterministic verdict
AI document and research facts, associations, interpretations, and findings MUST NOT change score weights or the four-band result. The scoring boundary SHALL accept only facts explicitly marked as code-owned and validated against source evidence.

#### Scenario: AI reports a high-importance inconsistency
- **WHEN** AI marks a finding as high importance
- **THEN** the system shows it for human review
- **AND** calculates score and band only from code-owned fixed-rule facts

#### Scenario: AI returns a value that conflicts with a code-owned fact
- **WHEN** an AI-derived value differs from a code-owned deterministic fact
- **THEN** the report shows the discrepancy for human review without replacing the code-owned score input

### Requirement: Requested location signals
The report SHALL contain a code-owned phone-country result and stated-city-or-address result when deterministic extraction can identify them without guessing. It SHALL check whether the locality exists and identify its country when versioned offline reference data allows it. It SHALL show flags for an explicit phone country outside the EU, an atypical or small stated locality outside the EU, and a combined `location_outside_eu` observation based only on available code-owned evidence.

#### Scenario: Explicit phone prefix points outside the EU
- **WHEN** a parsed international phone number maps unambiguously to a non-EU country
- **THEN** the report shows the requested phone-country flag, parsed country evidence, and extractor version

#### Scenario: Phone country requires a default region
- **WHEN** a phone country cannot be determined without assuming a default region
- **THEN** the report keeps the phone country unknown and does not score it

#### Scenario: Stated locality can be resolved
- **WHEN** deterministic code resolves the stated city or address to one country
- **THEN** the report shows the resolved location, reference-data version, and whether the requested non-EU or atypical-locality flag applies

#### Scenario: Stated locality cannot be resolved
- **WHEN** deterministic code cannot confirm that the stated locality exists or maps to one country
- **THEN** the report shows a location-validation observation with the attempted value and does not guess its country

#### Scenario: Location signals are combined
- **WHEN** code-owned phone and stated-location facts are available
- **THEN** the report includes a combined location observation with both evidence items and a disclaimer that they do not prove physical location
