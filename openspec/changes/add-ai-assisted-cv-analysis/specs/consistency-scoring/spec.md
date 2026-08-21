## MODIFIED Requirements

### Requirement: Config-driven weighted scoring
The system SHALL compute a 0-100 consistency score from `ScoringSignal` values created by fixed rules from validated, code-owned location facts. Weights SHALL be read from configuration and not hard-coded. Candidate extraction MUST NOT assign weights. AI-derived facts, associations, interpretations, and findings MUST NOT become weighted inputs. Slice 2A and Slice 2B MUST NOT change signal weights, minimum evidence requirements, or band thresholds without separate anonymous calibration and explicit project-owner approval.

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

#### Scenario: Slice 2 runs without approved calibration
- **WHEN** Slice 2A or Slice 2B removes or replaces prototype inputs and no separately approved calibration exists
- **THEN** the configured weights, minimum evidence requirement, and band thresholds remain unchanged
- **AND** insufficient mechanically defensible evidence produces the deterministic gray outcome

### Requirement: Explainable, reproducible report
The report SHALL contain the deterministic score, band, candidates, code-owned facts, observations, scoring signals, and rule findings. Each deterministic result SHALL include authority, evidence, extractor version, and any applicable reference-data version. It SHALL also contain available AI document findings, research findings, a summary, evidence, authority/source labels, and the settings that produced each section. The same redacted canonical input, deterministic extractor versions, reference-data versions, and ruleset MUST produce the same deterministic score, band, facts, observations, scoring signals, and rule findings. The system SHALL make AI sections auditable through stored model, prompt, schema, deterministic-observation, and evidence data.

#### Scenario: Itemized findings
- **WHEN** the system produces a report
- **THEN** each deterministic finding shows its observed value, claimed value, direction, weight, reason, authority, source evidence, extractor version, and any applicable reference-data version

#### Scenario: Itemized AI-assisted findings
- **WHEN** AI document or research findings are available
- **THEN** each finding shows its category, importance, confidence, reason, evidence, source location or URL, authority, and configuration version

#### Scenario: Deterministic output
- **WHEN** the system analyzes the same CV twice with the same deterministic extractor, reference data, and ruleset versions
- **THEN** both runs produce the same deterministic score, band, facts, and rule findings regardless of AI output

## ADDED Requirements

### Requirement: AI findings excluded from deterministic verdict
AI document and research facts, associations, interpretations, and findings MUST NOT change score weights or the four-band result. The scoring boundary SHALL accept only `ScoringSignal` values produced by fixed deterministic rules from facts explicitly marked as code-owned and validated against source evidence.

#### Scenario: AI reports a high-importance inconsistency
- **WHEN** AI marks a finding as high importance
- **THEN** the system shows it for human review
- **AND** calculates score and band only from code-owned fixed-rule facts

#### Scenario: AI returns a value that conflicts with a code-owned fact
- **WHEN** an AI-derived value differs from a code-owned deterministic fact
- **THEN** the report shows the discrepancy for human review without replacing the code-owned score input

### Requirement: Requested location signals
The report SHALL contain code-owned phone-country facts and an explicitly person-owned stated-city-or-address result when deterministic extraction can identify them without guessing. It SHALL resolve localities through versioned offline reference data without treating absence from the bounded index as proof that a place does not exist. It SHALL show flags for an aggregate explicit phone country outside the EU, an atypical or small stated locality outside the EU, and a combined `location_outside_eu` observation based only on available code-owned evidence. Postal compatibility SHALL remain an unweighted observation until separate calibration and explicit project-owner approval authorize a change.

#### Scenario: Explicit phone prefix points outside the EU
- **WHEN** every deterministically person-owned, valid, country-resolved international phone fact maps to the same non-EU country
- **THEN** the report shows one aggregate phone-country flag with every supporting fact, authority, evidence, extractor version, and applicable reference-data version

#### Scenario: Resolved phone countries conflict
- **WHEN** deterministically person-owned phone facts map to different countries
- **THEN** the report records an ambiguous aggregate observation and creates no phone scoring signal

#### Scenario: Phone country requires a default region
- **WHEN** a phone country cannot be determined without assuming a default region
- **THEN** the report keeps the phone country unknown and does not score it

#### Scenario: Stated locality can be resolved
- **WHEN** deterministic code resolves the stated city or address to one country
- **THEN** the report shows the resolved location, reference-data version, and whether the requested non-EU or atypical-locality flag applies

#### Scenario: Stated locality cannot be resolved
- **WHEN** deterministic code cannot find the stated locality in the bounded offline index or cannot map it to one country
- **THEN** the report shows an unresolved or ambiguous location observation with the attempted value and does not guess its country or claim the place is nonexistent

#### Scenario: Postal compatibility is present
- **WHEN** deterministic extraction records postal compatibility
- **THEN** the report shows it as an observation with zero scoring weight
- **AND** score and band remain unchanged by that observation

#### Scenario: Location signals are combined
- **WHEN** code-owned phone and stated-location facts are available
- **THEN** the report includes a combined location observation with both evidence items and a disclaimer that they do not prove physical location
