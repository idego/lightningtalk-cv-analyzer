## Purpose

Defines AI review of one CV. The review gives recruiters cited findings before optional web research starts.

## ADDED Requirements

### Requirement: Bounded document analysis
The system SHALL send each supported CV to one bounded AI analysis. The request SHALL contain extracted document text and no web access. The result SHALL match a defined schema.

#### Scenario: Successful AI document analysis
- **WHEN** a supported CV has enough extractable text
- **THEN** the system sends that CV's prepared text for AI analysis
- **AND** accepts only a result that matches the configured schema

#### Scenario: Independent candidate context
- **WHEN** the system analyzes multiple CVs
- **THEN** each analysis contains only the current CV and versioned instructions

### Requirement: Complete reviewer-support output
The AI analysis SHALL find relevant facts, conflicts, missing data, suspicious patterns, and candidates for optional company, education/certification, or LinkedIn research.

#### Scenario: Potential issue found in the CV
- **WHEN** the model finds a source-backed conflict or suspicious pattern
- **THEN** it returns the category, reason, importance, confidence, page, and exact source excerpt

#### Scenario: Information is absent or uncertain
- **WHEN** the source does not support a confident result
- **THEN** the model returns an explicit unknown or uncertainty state

### Requirement: Evidence required for document findings
The system MUST NOT present an AI finding as fact unless the finding cites a location in the submitted CV.

#### Scenario: Finding lacks evidence
- **WHEN** an AI finding has no usable page and source excerpt
- **THEN** the system excludes it from factual findings or marks it for manual review

### Requirement: Protected reviewer-support boundaries
The AI MUST NOT infer or score nationality, ethnicity, appearance, or origin from a name, photo, foreign school, language, or other proxy. It MUST NOT reject or advance a candidate.

#### Scenario: Unsupported demographic inference
- **WHEN** CV content could lead to a demographic inference
- **THEN** the system does not emit that inference as a finding or scoring signal

#### Scenario: AI analysis completes
- **WHEN** AI analysis returns findings
- **THEN** the system sends them to a human reviewer and makes no hiring decision

### Requirement: Versioned analysis configuration
Each AI result SHALL record its provider, model, prompt version, schema version, reasoning setting, and usage data.

#### Scenario: AI result persisted
- **WHEN** the system stores an AI result
- **THEN** it stores the analysis settings and usage data with that result
