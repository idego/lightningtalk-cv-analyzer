## ADDED Requirements

### Requirement: Legacy score isolation from file and link inspection
The existing deterministic location score and four-band result SHALL remain backward-compatible legacy report fields during this change. File metadata, link-check outcomes, `SUSPICIOUS` flags, and `UNAVAILABLE` results MUST NOT change score, band, thresholds, or weights. The frontend MUST NOT present the legacy score or band as the overall assessment of the CV or candidate.

#### Scenario: Suspicious link is found
- **WHEN** file/link inspection emits one or more `SUSPICIOUS` flags
- **THEN** the serialized legacy score and band remain identical to the result produced without file/link inspection

#### Scenario: Existing API consumer reads score fields
- **WHEN** a report is serialized during the compatibility period
- **THEN** existing score and band fields remain available with their previous location-consistency semantics
