## ADDED Requirements

### Requirement: Exclude exact quarantined evidence before signal materialization

Deterministic candidate extraction SHALL consume the shared versioned visibility-exclusion index. Any evidence span intersecting an exact quarantined interval SHALL be inadmissible for candidate ownership, facts, observations that expose the source value, and scoring signals. A normalized literal with both hidden and independently visible evidence MAY remain supported only by its visible evidence. Partial or unmapped presentation evidence SHALL not remove canonical text but SHALL produce honest partial coverage.

The exclusion policy SHALL apply to phone, location, postal, date, email, URL, right-to-work, national-ID presence disclosure, and any new structured candidate category before aggregation or deduplication. Mandatory national-ID redaction remains authoritative and excluded national-ID characters MUST NOT be exposed through quarantine diagnostics.

#### Scenario: Hidden phone and visible phone disagree
- **WHEN** one valid person phone occurs only in an exact quarantined span and another occurs visibly
- **THEN** only the visible phone may contribute facts and aggregate signals

#### Scenario: Equivalent literal is hidden and visible
- **WHEN** the same normalized candidate occurs in hidden and visible source locations
- **THEN** deduplication retains only independently visible evidence on the admitted candidate

#### Scenario: Exclusion association is partial
- **WHEN** a presentation signal cannot be exactly mapped to the candidate span
- **THEN** code does not remove the candidate solely from that uncertain mapping and reports partial visibility coverage
