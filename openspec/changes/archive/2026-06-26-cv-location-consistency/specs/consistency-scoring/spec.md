## ADDED Requirements

### Requirement: Config-driven weighted scoring
The system SHALL compute a 0–100 consistency score by aggregating each signal's weighted vote for or against the claimed location, where weights are read from configuration and not hard-coded.

#### Scenario: Signals agree with claim
- **WHEN** the extracted signals are consistent with the claimed location
- **THEN** the system produces a high score reflecting agreement

#### Scenario: Strong signal conflicts with claim
- **WHEN** a strong signal (e.g. phone country) conflicts with the claimed location
- **THEN** the conflict lowers the score by its configured weight

#### Scenario: Weights changed via configuration
- **WHEN** signal weights are updated in configuration
- **THEN** scoring reflects the new weights without code changes

### Requirement: Four-band classification
The system SHALL classify each result into exactly one of four bands: green (signals present and agree), amber (some conflict), red (strong or multiple conflict), and gray (insufficient evidence). A CV with too few signals MUST be classified gray, never green.

#### Scenario: Sparse CV
- **WHEN** the CV yields too few location signals to assess the claim
- **THEN** the system classifies the result as gray (insufficient evidence) and routes it to a human

#### Scenario: Clear conflict
- **WHEN** strong or multiple signals conflict with the claim
- **THEN** the system classifies the result as red

#### Scenario: Bias toward flagging under uncertainty
- **WHEN** the result is borderline between two bands
- **THEN** the system selects the band that routes the candidate to human review

### Requirement: Explainable, reproducible report
The system SHALL produce a report containing the score, band, an itemized list of findings (signal, observed value, claimed value, agreement direction, weight, rationale), and a plain-language summary. Given the same input and ruleset version, the report MUST be reproducible.

#### Scenario: Itemized findings
- **WHEN** a report is produced
- **THEN** each contributing signal appears as a finding with observed value, claimed value, agreement direction, weight, and a one-line rationale

#### Scenario: Deterministic output
- **WHEN** the same CV is analyzed twice under the same ruleset version
- **THEN** the system produces identical score, band, and findings

### Requirement: Decision-support framing
The system MUST NOT auto-reject or auto-advance candidates and SHALL stamp every report as decision-support, not automated rejection.

#### Scenario: No automated decision
- **WHEN** a report is produced for any band including red
- **THEN** the system returns the report for human review and takes no adverse automated action
