## MODIFIED Requirements

### Requirement: Bounded document analysis

The system SHALL send each supported CV to one bounded AI analysis only after Slice 3 is explicitly enabled. The request SHALL accept the redacted document type and SHALL contain its complete page-aware visible-source text, stable page IDs, versioned deterministic observations for that CV, and no web access. Complete visible-source text means the canonical redacted lines with exact quarantined hidden/strongly-low-visibility intervals replaced by same-length masks before request serialization; line IDs and source offsets SHALL remain stable. It MUST NOT accept the raw document type. Raw national-ID values and quarantined source characters MUST NOT enter the request. The result SHALL match a defined schema.

Every returned AI field or finding SHALL be rejected when any required evidence intersects a quarantined source interval, including when the model reconstructs or repeats the hidden value from other context. Such rejected material MUST NOT become a persisted AI fact, reviewer finding, research subject, request input, cache key, log, or exception message.

#### Scenario: Successful AI document analysis
- **WHEN** a supported CV has enough extractable text
- **THEN** the system sends that CV's redacted prepared visible-source text and deterministic observations for AI analysis
- **AND** accepts only a result that matches the configured schema and uses non-quarantined evidence

#### Scenario: Independent candidate context
- **WHEN** the system analyzes multiple CVs
- **THEN** each analysis contains only the current CV, observations derived from that CV, and versioned instructions

#### Scenario: Deterministic extractor misses content
- **WHEN** a relevant fact appears in the complete visible-source CV text but not in the supplied deterministic observations
- **THEN** the AI can still analyze the non-quarantined source text and cite the omitted content for human review

#### Scenario: Hidden content has a stable source line
- **WHEN** a model response cites a source line whose required evidence intersects an exact quarantined interval
- **THEN** the field or finding is rejected even though the line ID exists
- **AND** no hidden value is admitted to research or persistence

## ADDED Requirements

### Requirement: Enrich rather than replace code-owned document understanding

The AI request SHALL include bounded code-owned section, structured-entry, ambiguous-span, and missing-field context when available, in addition to the complete redacted visible-source projection and existing deterministic observations. AI MAY propose missing entries, field values, or alternative grouping for reviewer support, but it MUST NOT delete, downgrade, or relabel a code-owned entry. Every accepted AI field SHALL continue to pass independent canonical non-quarantined source validation and remain outside deterministic score and band calculation.

Reconciliation SHALL retain code-owned and AI-derived authority per field, merge only compatible records with supported identity evidence, and expose conflicts as uncertainty for human review. An unavailable, failed, or partially valid AI response SHALL leave the complete code-owned understanding result usable.

#### Scenario: AI returns no education
- **WHEN** code-owned understanding contains education entries and AI returns none
- **THEN** the code-owned entries remain present and usable by downstream research

#### Scenario: AI fills a missing optional field
- **WHEN** AI supplies an optional field with valid source-line evidence for an existing code-owned entry
- **THEN** the reconciled entry may display the AI-derived field with its distinct authority
- **AND** the original code-owned fields remain unchanged

#### Scenario: AI conflicts with a code-owned field
- **WHEN** AI supplies a supported value that conflicts with an independently supported code-owned value
- **THEN** the system retains the code-owned field and exposes the conflict as reviewer uncertainty
- **AND** does not silently overwrite either source account

#### Scenario: AI analysis fails
- **WHEN** the provider call fails or its response is unusable
- **THEN** document understanding, structural audit, research eligibility from code-owned subjects, score, and band remain available
