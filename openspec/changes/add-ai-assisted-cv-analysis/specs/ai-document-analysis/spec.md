## Purpose

Defines AI review of one CV. The review interprets document semantics and gives recruiters cited findings before optional web research starts. It does not own deterministic verdict inputs.

## ADDED Requirements

### Requirement: Bounded document analysis
The system SHALL send each supported CV to one bounded AI analysis only after Slice 3 is explicitly enabled. The request SHALL accept the redacted document type and SHALL contain its complete page-aware text, stable page IDs, versioned deterministic observations for that CV, and no web access. It MUST NOT accept the raw document type. Raw national-ID values MUST NOT enter the request. The result SHALL match a defined schema.

#### Scenario: Successful AI document analysis
- **WHEN** a supported CV has enough extractable text
- **THEN** the system sends that CV's redacted prepared text and deterministic observations for AI analysis
- **AND** accepts only a result that matches the configured schema

#### Scenario: Independent candidate context
- **WHEN** the system analyzes multiple CVs
- **THEN** each analysis contains only the current CV, observations derived from that CV, and versioned instructions

#### Scenario: Deterministic extractor misses content
- **WHEN** a relevant fact appears in the complete CV text but not in the supplied deterministic observations
- **THEN** the AI can still analyze the source text and cite the omitted content for human review

### Requirement: Complete reviewer-support output
The AI analysis SHALL find relevant semantic facts, conflicts, missing data, suspicious patterns, and candidates for optional company, education/certification, or LinkedIn research.

#### Scenario: Potential issue found in the CV
- **WHEN** the model finds a source-backed conflict or suspicious pattern
- **THEN** it returns the category, reason, importance, confidence, page, and exact source excerpt

#### Scenario: Information is absent or uncertain
- **WHEN** the source does not support a confident result
- **THEN** the model returns an explicit unknown or uncertainty state

### Requirement: Structured semantic CV facts requested by HR
The AI analysis SHALL return structured education and employment facts when present, including institutions, programs, companies, roles, dates, locations, and explicit relationship types. It MAY associate or interpret contact candidates for human review. The complete report SHALL take authoritative phone and stated-location facts from the deterministic section when code can resolve them unambiguously. AI-derived contact interpretations SHALL remain separately identified and MUST NOT replace missing deterministic score inputs.

#### Scenario: Education or employment facts are present
- **WHEN** the CV contains education or employment information
- **THEN** the result returns the requested fields with page and source excerpts

#### Scenario: Contact candidate is semantically ambiguous
- **WHEN** the document contains several phone or location candidates with unclear ownership
- **THEN** the AI may explain the possible association for human review
- **AND** the result marks that interpretation as AI-derived and non-scoring

#### Scenario: Requested semantic fact is missing
- **WHEN** one of the requested fields is absent or unclear
- **THEN** the field is explicitly marked as unknown instead of being guessed

### Requirement: Evidence required for document findings
The system MUST NOT present an AI finding as fact unless the finding cites a location in the submitted CV.

#### Scenario: Finding lacks evidence
- **WHEN** an AI finding has no usable page and source excerpt
- **THEN** the system excludes it from factual findings or marks it for manual review

#### Scenario: Finding cites the wrong page
- **WHEN** an excerpt is absent from the cited page's canonical source text
- **THEN** the system rejects that evidence item

### Requirement: AI excluded from deterministic authority
AI-derived facts, associations, interpretations, and findings MUST NOT become inputs to deterministic score or band calculation. Deterministic arithmetic over AI-derived semantic facts MAY create an AI-assisted finding, but that finding SHALL remain outside the verdict path.

#### Scenario: AI selects a plausible claimed location
- **WHEN** deterministic code marked the claimed location as undetermined and AI returns a plausible interpretation
- **THEN** the system shows the interpretation for human review
- **AND** keeps the deterministic scoring claim undetermined

#### Scenario: Code calculates a timeline overlap from AI facts
- **WHEN** code calculates an overlap from AI-extracted employment dates
- **THEN** the system labels the result as AI-assisted and does not change the score or band

### Requirement: Protected reviewer-support boundaries
The AI MUST NOT infer or score nationality, ethnicity, appearance, or origin from a name, photo, foreign school, language, or other proxy. It MUST NOT reject or advance a candidate.

#### Scenario: Unsupported demographic inference
- **WHEN** CV content could lead to a demographic inference
- **THEN** the system does not emit that inference as a finding or scoring signal

#### Scenario: AI analysis completes
- **WHEN** AI analysis returns findings
- **THEN** the system sends them to a human reviewer and makes no hiring decision

### Requirement: Versioned analysis configuration
Each AI result SHALL record its provider, model, prompt version, schema version, reasoning setting, deterministic-observation version, and usage data.

#### Scenario: AI result persisted
- **WHEN** the system stores an AI result
- **THEN** it stores the analysis settings, deterministic-observation version, and usage data with that result
