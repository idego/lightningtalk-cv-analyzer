# ai-document-analysis Specification

## Purpose
Defines AI review of one CV. The review interprets document semantics and gives recruiters cited findings before optional web research starts. It does not own deterministic verdict inputs.

## Requirements

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
The system MUST NOT present an AI finding as fact unless the finding cites a
stable page-scoped source-line ID from the submitted CV. Code SHALL resolve each
accepted line ID to its canonical redacted page and materialize the exact source
excerpt. The model SHALL NOT be trusted to reproduce or normalize candidate
text as evidence.

#### Scenario: Finding lacks evidence
- **WHEN** an AI finding has no usable page and source excerpt
- **THEN** the system excludes it from factual findings or marks it for manual review

#### Scenario: Finding cites the wrong page
- **WHEN** a source-line ID is unknown or does not belong to the cited page
- **THEN** the system rejects that evidence item

#### Scenario: Valid source line is cited
- **WHEN** a model result cites a known line ID on its owning page
- **THEN** code adds the canonical redacted line text as the exact excerpt
- **AND** downstream report and persistence use that code-materialized evidence

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

#### Scenario: Candidate name changes without other evidence changing
- **WHEN** two otherwise identical CVs differ only in the literal candidate name
- **THEN** deterministic findings, counts, score, band, and research-category eligibility remain unchanged
- **AND** only the neutral name fact and candidate-scoped LinkedIn discovery query may contain the changed name
- **AND** no missing or ambiguous public profile becomes negative evidence

#### Scenario: AI analysis completes
- **WHEN** AI analysis returns findings
- **THEN** the system sends them to a human reviewer and makes no hiring decision

### Requirement: Versioned analysis configuration
Each AI result SHALL record its provider, model, prompt version, schema version, reasoning setting, deterministic-observation version, and usage data.

#### Scenario: AI result persisted
- **WHEN** the system stores an AI result
- **THEN** it stores the analysis settings, deterministic-observation version, and usage data with that result

### Requirement: Lean model contract and code-owned report derivation
The model response SHALL contain only source-grounded values, source-line IDs,
unknowns, limitations, and reviewer findings. It SHALL NOT contain authority,
source, code-owned excerpts, check IDs, checklist counts, or research
candidates. Education and employment facts SHALL carry independent
`{value,line_ids}` evidence for every field. Code SHALL materialize excerpts,
deduplicate evidence, assign finding check ownership, build the complete
checklist and derive research candidates only from accepted facts.

#### Scenario: Code owns bookkeeping
- **WHEN** a lean response contains an accepted education or employment field
- **THEN** the persisted report contains code-assigned authority/source,
  materialized excerpts, a complete checklist, and only derivable research
  candidates
- **AND** model-supplied bookkeeping fields are rejected by the strict schema

### Requirement: Field-level fail-closed validation
The validator SHALL validate each fact field and evidence item independently.
An unsupported optional field SHALL become unknown and may produce a neutral
partial-validation warning while valid fields, facts, and usable findings
remain visible. A missing required identity field SHALL reject that composite
fact. Root schema failures, protected-boundary violations, and unusable finding
evidence SHALL reject the response. The warning SHALL use the neutral message
`Część danych nie została pokazana, ponieważ nie udało się potwierdzić ich w
tekście CV.`

#### Scenario: Optional field cannot be confirmed
- **WHEN** an education or employment optional field cites a line that does not
  support its literal value
- **THEN** code clears that field, keeps independently supported fields and
  usable findings, and exposes the partial-validation warning

#### Scenario: Protected boundary or finding evidence is unusable
- **WHEN** a response contains a hiring/demographic conclusion or a finding
  without valid source-line evidence
- **THEN** the whole response fails closed without exposing model text in the
  diagnostic

### Requirement: Independent evaluation metrics
The offline harness SHALL report schema validity, line-reference validity,
per-field fact support, semantic finding recall/evidence, and unexpected
finding quality as separate metrics. Invalid fact fields MUST NOT erase valid
finding recall or finding line-reference metrics. Supported unexpected findings
require manual `useful`, `neutral`, or `noise` classification; they SHALL NOT be
an automatic failure solely because they are unexpected. The initial four-case
gate MAY accept at most one evidence-backed, non-`attention` noise finding per
two CVs. Unsupported findings, invalid evidence, forbidden output, and missed
expected findings SHALL have zero tolerance. The initial regression set SHALL
use four anonymous CVs and any held-out raw CV manifest SHALL remain ignored and
untracked.

#### Scenario: Invalid fact field does not erase finding metrics
- **WHEN** a response contains an unsupported education or employment field and
  a supported semantic finding
- **THEN** the harness reports the field-support result separately while
  retaining the finding recall and finding line-reference result

### Requirement: Bounded and diagnosable AI retries
The system SHALL keep the deterministic report available when AI analysis fails. It SHALL distinguish retryable transport failures from non-retryable client failures and invalid model responses. The configurable defaults SHALL allow one retry for retryable transport failures, one fresh retry for an invalid model response, and no more than three total attempts including the initial attempt. The request timeout SHALL remain 120 seconds and the output limit SHALL remain 4,096 tokens. Safe diagnostics MAY store failure stage, HTTP status class, provider request ID, attempt count, prompt/schema versions, and latency, but MUST NOT store or log CV content or model-response text.

#### Scenario: Retryable transport failure occurs
- **WHEN** an attempt times out or receives HTTP 429 or 5xx
- **THEN** the system may retry within the configured transport and total limits

#### Scenario: Non-retryable client failure occurs
- **WHEN** an attempt receives a non-429 4xx response
- **THEN** the system does not retry it automatically and preserves the deterministic report

#### Scenario: Model response is invalid
- **WHEN** schema, protected-boundary, or evidence validation rejects a model response
- **THEN** the system may make one fresh attempt within the configured invalid-response and total limits
- **AND** diagnostics do not retain the rejected response text

#### Scenario: A later attempt fails after a model response used tokens
- **WHEN** an invalid response records usage and a later transport or non-retryable client attempt fails
- **THEN** the final safe failure keeps cumulative usage and the total attempt count without retaining response text

#### Scenario: Recruiters submit the same manual retry concurrently
- **WHEN** multiple owner-authorized requests retry one analysis while the first retry is in flight
- **THEN** they join one in-flight operation and receive the same success or failure outcome
- **AND** concurrency does not create another provider operation or a post-success conflict response

### Requirement: Material document-artifact findings
The AI SHALL report a `document_artifact` only when malformed source text blocks extraction of an important fact or materially changes the apparent meaning. The typed response SHALL classify the material effect and the affected fact through closed code-owned fields. The validator SHALL suppress a finding when this structural declaration is absent or non-material, regardless of marker characters or model prose. Understandable formatting defects, spacing, line wrapping, concatenation, question marks, HTML-like tags, and entities SHALL NOT produce this finding by themselves.

#### Scenario: Extraction defect remains understandable
- **WHEN** malformed or concatenated text preserves the useful fact and meaning
- **THEN** the AI does not emit a `document_artifact` finding

#### Scenario: Marker characters do not block meaning
- **WHEN** source text contains `??`, an HTML-like tag, or an entity but the typed material effect is `none`
- **THEN** code suppresses the finding without interpreting reviewer prose

#### Scenario: Extraction defect blocks meaning
- **WHEN** malformed source text prevents an important fact from being read or materially changes its meaning
- **THEN** the AI may emit a source-grounded `document_artifact` finding for human review
- **AND** the typed finding identifies `important_fact_unreadable` or `meaning_changed` and a closed affected-fact category

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
