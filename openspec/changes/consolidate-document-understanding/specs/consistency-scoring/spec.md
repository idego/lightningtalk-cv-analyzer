## ADDED Requirements

### Requirement: Preserve visible-source verdict behavior and reject hidden-only inputs

The consolidated understanding pass MUST NOT create a new scoring-signal kind, modify `weights.yaml`, alter thresholds, or admit education, employment, skills, AI facts, or research into score and band calculation. For fixtures whose authorized evidence is visible and unchanged, deterministic candidates, facts, observations, scoring signals, findings, numeric score, band, and minimum-evidence handling SHALL remain byte-equivalent for the same ruleset.

An existing signal candidate supported exclusively by exact quarantined hidden or strongly low-visibility evidence SHALL be removed before scoring as an intentional safety correction. Its removal MUST NOT be described as evidence that the underlying claim is false or absent.

#### Scenario: Ordinary visible CV is reanalyzed
- **WHEN** all authorized scoring evidence is visible and source-equivalent to the pre-consolidation fixture
- **THEN** the complete deterministic and verdict projections are byte-equivalent

#### Scenario: Hidden-only signal would change the verdict
- **WHEN** a location, phone, or postal candidate is supported exclusively by exact quarantined evidence
- **THEN** it does not enter score, band, findings, signal count, or minimum-evidence calculation
