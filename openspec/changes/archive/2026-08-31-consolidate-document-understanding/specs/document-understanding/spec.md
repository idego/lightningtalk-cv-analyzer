## Purpose

Defines one evidence-first, code-owned understanding pass that identifies CV sections, structured entries, dates, skills, and reusable research subjects without making AI the sole source of document structure.

## ADDED Requirements

### Requirement: Produce one versioned document-understanding result

For each accepted redacted CV, the system SHALL produce one versioned document-understanding result from the canonical source model. The result SHALL contain coverage, detected sections, normalized date ranges, structured entries, ambiguous spans, and code-owned research subjects. Every positive result SHALL retain exact or partial source association through stable page and line identifiers; an unmapped or unsupported span MUST NOT become a positive structured fact. The same redacted document, snapshot month, ruleset, parser versions, and reference-data versions SHALL produce the same ordered result.

The understanding result SHALL extend the existing deterministic result and structural-audit projections rather than replace their public contracts. It MUST NOT create a `ScoringSignal`, modify scoring weights or thresholds, or change visible-input score and band results merely because additional document structure was recognized.

#### Scenario: AI is disabled
- **WHEN** a supported CV is analyzed with AI disabled
- **THEN** the system still returns its code-owned sections, supported structured entries, skills, date ranges, and research subjects
- **AND** deterministic scoring continues to use only its previously authorized scoring signals

#### Scenario: The same document is analyzed reproducibly
- **WHEN** the same redacted document is analyzed with the same snapshot and versioned configuration
- **THEN** section, entry, field, evidence, confidence, and research-subject ordering is stable

#### Scenario: Source association is unavailable
- **WHEN** a possible value cannot be associated with canonical redacted source evidence
- **THEN** it is omitted or retained as an ambiguous non-fact
- **AND** it cannot become a research subject or scoring input

### Requirement: Quarantine hidden and strongly low-visibility source values

Before code materializes candidates, structured fields, research subjects, or scoring inputs, the system SHALL create one visibility-exclusion index from exact-mapped source spans carrying a supported high-confidence hidden or strongly low-visibility trigger. A candidate evidence span that intersects an exact exclusion interval at any character SHALL be inadmissible. A positive value SHALL require at least one complete independently supporting evidence span that does not intersect an exclusion interval. The system SHALL retain a bounded neutral visibility observation and coverage rather than expose excluded evidence as an ordinary CV claim.

For a multi-field or multi-span record, every required identity/ownership field SHALL independently satisfy the admissible-evidence rule. A hidden label paired with a visible value MUST NOT establish the labelled ownership; the visible literal may remain an unowned candidate. When the same normalized literal appears once hidden and once visibly, only the visible evidence may support and be retained on the positive value. Deduplication and grouping MUST NOT merge excluded evidence back into an admitted value.

Unknown, partial, or unmapped presentation associations MUST NOT cause visible canonical text to be removed. Mandatory national-ID redaction remains prior to visibility disclosure. The quarantine policy and thresholds SHALL be versioned and SHALL apply consistently to document understanding and existing deterministic candidate materialization.

#### Scenario: Hidden phone is the only conflicting signal
- **WHEN** a phone value exists only in an exact-mapped hidden or strongly low-visibility span
- **THEN** it does not create a person-phone fact or scoring signal and cannot change score or band
- **AND** the visibility audit retains a safe observation without exposing prohibited sensitive text

#### Scenario: Hidden organization or institution is present
- **WHEN** a public entity name exists only inside an excluded visibility span
- **THEN** it does not become a structured entry identity or research subject

#### Scenario: Presentation association is uncertain
- **WHEN** a low-visibility presentation span is partial or unmapped and exclusion would remove otherwise visible canonical text without exact support
- **THEN** the system reports partial coverage and does not quarantine the canonical value solely from that uncertain association

#### Scenario: Evidence partially overlaps a hidden interval
- **WHEN** any character of a candidate evidence span intersects an exact exclusion interval
- **THEN** that evidence span is inadmissible and cannot support a positive field, subject, or scoring input

#### Scenario: Hidden label has a visible value
- **WHEN** a hidden relationship or ownership label precedes an otherwise visible literal value
- **THEN** code does not use the hidden label to assign person, employer, education, or other ownership
- **AND** the visible literal may remain an unowned non-scoring candidate

#### Scenario: The same literal is hidden and visible
- **WHEN** equivalent normalized text has both excluded and independently visible source occurrences
- **THEN** the visible occurrence may support the result and excluded evidence is not retained or merged into it

### Requirement: Detect a bounded standard CV section catalog

The system SHALL detect section spans from source order, versioned multilingual heading aliases, and available source presentation evidence. The standard catalog SHALL include `contact`, `summary`, `employment`, `education`, `skills`, `certifications`, `projects`, `languages`, `publications`, `awards`, `volunteering`, `references`, and `other`. Each section SHALL record its category, heading evidence, bounded source range, confidence, and detector version. A section SHALL end at the next accepted peer heading or at the end of the document surface.

Exact heading aliases MAY establish a section from canonical text alone. Fuzzy similarity or presentation style MUST NOT establish a section independently; it may only strengthen a result that also has contextual evidence. Unknown headings SHALL remain `other` or ambiguous. The system MUST NOT invent sections, columns, table relationships, or entry ownership when source evidence is insufficient.

#### Scenario: Recognized education heading is present
- **WHEN** a canonical line contains a supported education heading alias and the following content precedes the next accepted peer heading
- **THEN** the system records one education section with heading and bounded content evidence

#### Scenario: Standard non-timeline section is present
- **WHEN** a CV contains a supported Skills, Certifications, Projects, Languages, Publications, Awards, Volunteering, or References heading
- **THEN** the system classifies the corresponding bounded section independently of AI

#### Scenario: Styling alone resembles a heading
- **WHEN** a short bold or large-font line lacks sufficient lexical and contextual heading evidence
- **THEN** styling alone does not establish a standard section

#### Scenario: Heading is uncertain
- **WHEN** a heading-like span cannot be assigned to one standard category without guessing
- **THEN** the system retains it as `other` or ambiguous with source evidence
- **AND** does not assign its content to education or employment facts

### Requirement: Use shared date and entry annotations

The system SHALL create date spans and normalized date ranges once per document and reuse them for candidate disclosure, structured entries, and structural timeline projection. Date normalization SHALL preserve the source literal, endpoint precision, snapshot month for open-ended ranges, parser version, and validation status. A malformed or unsupported date-like value SHALL remain invalid or unresolved instead of being silently normalized.

Within accepted sections, the system SHALL use one shared entry-boundary mechanism based on source order and available paragraph, list, table-row, indentation, date-anchor, and spacing evidence. Category schemas MAY select different fields from a shared entry span, but MUST NOT independently rediscover section boundaries or reparse the entire document.

#### Scenario: Timeline and education use the same range
- **WHEN** a supported date range occurs in an accepted education entry
- **THEN** the structured entry and structural timeline reference the same normalized range and canonical evidence

#### Scenario: Entry boundary is uncertain
- **WHEN** adjacent source blocks cannot be grouped into one or several entries without guessing
- **THEN** the system retains the bounded content as ambiguous
- **AND** does not invent an institution, employer, program, role, or relationship

#### Scenario: Existing invalid period is encountered
- **WHEN** a shared date range contains an invalid month or starts after its end
- **THEN** all projections preserve the same invalid status and source evidence
- **AND** no projection treats it as a valid duration

### Requirement: Materialize code-owned education and employment entries conservatively

The system SHALL materialize structured education and employment entries from accepted section and entry spans. An education entry MAY contain institution, program, degree, study dates, result, and location fields. An employment entry MAY contain organization, role, relationship type, employment dates, and location fields. Every populated field SHALL have independent canonical evidence, authority `code`, extractor version, and confidence. A field absent from or unsupported by the source SHALL remain unknown.

A high-confidence education entry SHALL require an accepted education section and a source-supported institution indicator, plus at least one independently supported program, degree, or study-date field. A high-confidence employment entry SHALL require an accepted employment section and a source-supported organization or explicit self-employment relationship, plus at least one independently supported role or employment-date field. Lower-confidence entries MAY be retained for review but MUST NOT automatically become research subjects unless their required public entity field is independently supported.

`Self-Employed`, `Freelance`, and equivalent relationship labels SHALL be represented as relationship types and MUST NOT be materialized as organization names unless the same entry names a distinct business, client, or employer.

#### Scenario: Education entry is explicit
- **WHEN** an accepted education section contains a supported institution and independently supported degree, program, or date field
- **THEN** the system returns a code-owned education entry with field-level evidence and confidence

#### Scenario: Employment entry is explicit
- **WHEN** an accepted employment section contains a supported organization and independently supported role or date field
- **THEN** the system returns a code-owned employment entry with field-level evidence and confidence

#### Scenario: Optional field is absent
- **WHEN** an entry supports its required identity field but not one optional field
- **THEN** the entry remains usable and the optional field is unknown

#### Scenario: Self-employment has no named organization
- **WHEN** an employment entry describes freelance or self-employed work without naming a distinct organization
- **THEN** code records the relationship without creating an organization research subject

### Requirement: Preserve stable record identity and explicit relationships

Each section, structured entry, date range, and research subject SHALL have a deterministic stable identifier derived from its document-scoped source identity, category, and source position rather than from translated display text. A structured entry SHALL reference its owning section and applicable date range identifiers explicitly. Structural timeline and UI projections MUST use these identifiers and MUST NOT join an employer, institution, or role to a timeline entry solely by normalized date-string equality.

#### Scenario: Two entries use the same dates
- **WHEN** two employment or education entries have identical displayed date ranges
- **THEN** each retains a distinct stable record identifier and explicit date-range relationship
- **AND** UI projection does not attach either entry's organization or institution by date text alone

#### Scenario: Display formatting changes
- **WHEN** localization or presentation changes the rendered form of a date or heading without changing source identity
- **THEN** record relationships remain stable

### Requirement: Extract explicit skills against versioned local reference data

The system SHALL extract explicitly stated skills from accepted skills sections and from clearly labelled skill lists within supported entries. Skill matching SHALL use a versioned local taxonomy and alias index with canonical identifiers, labels, language, source attribution, checksum manifest, and build version. Runtime analysis MUST NOT call an external taxonomy service or expose CV content to a reference-data provider.

Exact normalized phrases MAY produce a code-owned skill match in a skills section. Ambiguous short labels, including single-letter or ordinary-word technology names, SHALL require section and token-boundary context and MUST NOT match from unrelated prose. Fuzzy similarity MAY propose an ambiguous alias but MUST NOT independently create a code-owned skill fact. Duplicate aliases SHALL collapse to one canonical skill while preserving all supporting source evidence.

#### Scenario: Explicit skill list contains a known alias
- **WHEN** an accepted skills section contains an exact versioned alias with valid token boundaries
- **THEN** the system returns its canonical skill identifier, display label, source evidence, taxonomy version, and code authority

#### Scenario: Ambiguous short technology appears in prose
- **WHEN** a token such as `Go`, `R`, or `C` appears outside sufficient skills or labelled-list context
- **THEN** the system does not create a skill fact from that token alone

#### Scenario: Taxonomy is unavailable or invalid
- **WHEN** the configured taxonomy or manifest is unreadable, incompatible, or fails checksum validation
- **THEN** skill extraction reports unavailable coverage rather than silently returning a completed no-skill result
- **AND** the rest of CV analysis remains usable

### Requirement: Derive bounded research subjects from accepted structured entries

The system SHALL persist immutable company and education `code_research_subjects` projected from independently supported public-entity fields in code-owned structured entries. It MAY derive a per-request union with independently validated AI-only additions, but an AI omission, addition, retry, or failure MUST NOT delete, reorder, or suppress the persisted code-owned subjects. Request limits SHALL allocate capacity to code-owned subjects first in stable source order, followed by AI additions. Subjects SHALL be normalized, deduplicated, source-backed, and bounded by the existing per-category limits before any web research begins.

Skills, candidate PII, dates, results, and unconfirmed ambiguous values MUST NOT be included merely to form reusable public-entity cache keys. Existing exclusions for generic self-employment and freelance labels SHALL continue to apply.

#### Scenario: AI omits an explicit institution
- **WHEN** code extracts a supported institution and AI returns no education facts
- **THEN** education research remains available for the code-owned institution subject

#### Scenario: AI adds a supported institution
- **WHEN** AI returns an institution whose field evidence passes canonical source validation and code did not materialize it
- **THEN** the subject projection may include the validated addition without relabelling it as code-owned

#### Scenario: Code and AI return the same entity
- **WHEN** normalized code-owned and validated AI subjects identify the same public entity
- **THEN** the system emits one research subject with merged non-conflicting evidence and stable ordering

#### Scenario: AI additions exceed a research limit
- **WHEN** code-owned subjects already consume some or all of the category limit
- **THEN** AI additions use only remaining capacity and cannot displace a code-owned subject

### Requirement: Serialize an exact bounded document-understanding V1 contract

New reports SHALL expose a nullable top-level `document_understanding` object. When present it SHALL use `contract_version: document-understanding-v1` and contain exactly `contract_version`, `status`, `parser_version`, `ruleset_version`, `snapshot_month`, `coverage`, `sections`, `date_ranges`, `records`, `skills`, `ambiguous_spans`, `timeline_record_links`, `code_research_subjects`, and `truncation`. It MUST NOT serialize the canonical document, raw annotation text, internal annotation indexes, presentation properties, excluded source characters, provider responses, or whole-record cache inputs.

Every nested object SHALL reject unknown fields. The complete allowed values and shapes SHALL be:

```text
Status = completed | partial | unavailable | not_applicable
SourceFormat = pdf | docx | text
SectionKind = contact | summary | employment | education | skills |
  certifications | projects | languages | publications | awards |
  volunteering | references | other
RecordKind = education | employment
FieldName = institution | program | degree | study_dates | result |
  education_location | organization | role | relationship_type |
  employment_dates | employment_location
FieldStatus = supported | unknown | ambiguous
Confidence = high | medium | low
Association = exact | partial
DateStatus = valid | invalid | unresolved
DatePrecision = month | year | open_ended | unknown
ResearchCategory = company | education
AmbiguousCategory = section | date | entry | field | skill
AuditedPart = canonical_pages | source_blocks | presentation_spans |
  section_annotations | date_annotations | entry_annotations |
  skill_taxonomy
OmittedPart = docx_headers | docx_footers | docx_textboxes |
  docx_footnotes_endnotes | docx_comments | docx_drawings |
  docx_embedded_files | pdf_images_ocr | pdf_non_text_content |
  source_blocks_unavailable | presentation_spans_unavailable |
  sections_truncated | date_ranges_truncated | records_truncated |
  skills_unavailable | skills_truncated | ambiguous_spans_truncated |
  timeline_record_links_truncated | code_research_subjects_truncated

Evidence = {
  page_id: string, page_number: integer >= 1, line_id: string | null,
  start_offset: integer >= 0 | null, end_offset: integer >= 0 | null,
  association: Association, excerpt: string | null
}
Coverage = {
  status: Status, source_format: SourceFormat,
  audited_parts: unique AuditedPart[], omitted_parts: unique OmittedPart[]
}
Section = {
  id: string, kind: SectionKind, confidence: Confidence, heading: string,
  start_line_id: string, end_line_id: string, evidence: Evidence[]
}
DateRange = {
  id: string, source_literal: string,
  start_month: YYYY-MM | null, end_month: YYYY-MM | null,
  start_precision: DatePrecision, end_precision: DatePrecision,
  status: DateStatus, snapshot_month: YYYY-MM, evidence: Evidence[]
}
StructuredField = {
  name: FieldName, status: FieldStatus, value: string | null,
  authority: code, confidence: Confidence, evidence: Evidence[]
}
Record = {
  id: string, kind: RecordKind, section_id: string,
  confidence: Confidence, fields: StructuredField[],
  date_range_ids: string[]
}
Skill = {
  id: string, canonical_id: string, display_label: string,
  taxonomy: esco, taxonomy_version: string,
  confidence: Confidence, evidence: Evidence[]
}
AmbiguousSpan = {
  id: string, category: AmbiguousCategory,
  reason_code: string, evidence: Evidence[]
}
TimelineRecordLink = { timeline_entry_id: string, record_id: string }
CodeResearchSubject = {
  id: string, category: ResearchCategory, subject: string,
  record_id: string, field_name: institution | organization
}
TruncationRecord = {
  reported_count: integer >= 0,
  additional_count: integer >= 0,
  truncated: boolean
}
Truncation = {
  sections: TruncationRecord, date_ranges: TruncationRecord,
  records: TruncationRecord, skills: TruncationRecord,
  ambiguous_spans: TruncationRecord,
  timeline_record_links: TruncationRecord,
  code_research_subjects: TruncationRecord
}
```

The bounds SHALL be:

```text
sections <= 32; date_ranges <= 100; records <= 100; skills <= 200
ambiguous_spans <= 100; timeline_record_links <= 100
code_research_subjects <= 50; structured fields per record <= 8
date_range_ids per record <= 4
evidence items per section, field, skill, or ambiguous span <= 4
coverage audited_parts <= 16; coverage omitted_parts <= 32
every identifier, version, enum code, reason code, and taxonomy ID <= 128 chars
heading, skill display label, and date source literal <= 128 chars
structured field values and research subject values <= 256 chars
evidence excerpts <= 256 chars
```

`Record.fields` SHALL be an array with unique `name` values. Education records permit only `institution`, `program`, `degree`, `study_dates`, `result`, and `education_location`; employment records permit only `organization`, `role`, `relationship_type`, `employment_dates`, and `employment_location`. A `supported` field requires a non-null value and at least one admissible evidence item. An `unknown` field requires a null value and empty evidence. An `ambiguous` field uses a nullable value and at least one evidence item. Exact evidence association requires non-null offsets with `start_offset < end_offset`; partial association may use nullable offsets. Evidence excerpts contain only the bounded redacted non-quarantined source literal needed for reviewer display.

Truncation SHALL be dependency-aware. Sections and date ranges are retained first in stable source order. A record is retained only when its `section_id` and every listed `date_range_id` are retained; otherwise it is omitted and counted in `records.additional_count`. A timeline link is retained only when its record and referenced Structural Audit timeline entry are retained; a code research subject is retained only when its record and identity field are retained. Omitted dependent children increment their own collection's `additional_count`, set `truncated: true`, add the matching `OmittedPart`, and make overall and coverage status `partial`. Skills and ambiguous spans are independently retained by stable source order. All retained cross-references MUST resolve after truncation.

Arrays SHALL use stable source order, then stable ID. Invalid enum, shape, nullability, uniqueness, bound, evidence, cross-reference, or national-ID defense-in-depth validation SHALL reject the understanding object without logging its contents and preserve the otherwise usable legacy report surfaces.

#### Scenario: New report serializes understanding
- **WHEN** document understanding completes for a supported CV
- **THEN** the API and SQLite contain exactly the V1 allowlisted fields within every declared bound
- **AND** all record, section, date, timeline-link, and subject references resolve within the same payload or existing structural audit

#### Scenario: Internal data reaches serialization
- **WHEN** an implementation attempts to serialize the canonical document, raw annotation index, presentation metadata, excluded text, or an unknown field
- **THEN** the sanitizer rejects the understanding object without logging the rejected value

#### Scenario: V1 collection exceeds its limit
- **WHEN** one bounded collection exceeds its declared maximum
- **THEN** parent items are retained first in stable source order, dependent children with unresolved parents are omitted and counted in their own collections, and every retained cross-reference resolves
- **AND** coverage and overall status are partial with the applicable omitted-part codes

### Requirement: Preserve compatibility and disclose partial coverage

The document-understanding migration SHALL preserve existing readable reports and the existing public deterministic, structural-audit, file-detail, link-inspection, AI, and score/band contracts. New understanding fields MAY be absent from legacy reports. The same V1 sanitizer SHALL guard initial persistence, API serialization, report reload, and AI retry replacement. AI retry SHALL preserve the original understanding payload byte-for-byte.

The frontend and research projections SHALL prefer code-owned structured records for new reports and SHALL fall back to retained validated AI facts for legacy reports; the first migration version MUST NOT delete legacy AI facts. The system SHALL disclose per-surface coverage as completed, partial, unavailable, or not applicable and MUST NOT interpret no result as proof that a section or entry is absent.

The migration MUST preserve national-ID masking before understanding, AI, persistence, or logging. Committed evaluation fixtures MUST be synthetic or anonymous; private CVs and extracted HR text MUST remain ignored and untracked.

#### Scenario: Legacy report is reopened
- **WHEN** a report predating document understanding is loaded
- **THEN** existing report sections remain readable and missing understanding data is treated as unavailable rather than empty proof

#### Scenario: New understanding is enabled
- **WHEN** a CV previously used by deterministic scoring is analyzed through the consolidated pass
- **THEN** its visible-source authorized scoring inputs, numeric score, and band remain unchanged for the same ruleset
- **AND** an input sourced exclusively from quarantined hidden content is removed consistently before scoring as an intentional safety correction

#### Scenario: A document surface is unsupported
- **WHEN** relevant content may exist only in an unsupported or unmapped surface
- **THEN** coverage is partial or unavailable and the system does not claim that the corresponding category is absent

#### Scenario: AI retry replaces its own outcome
- **WHEN** a persisted analysis retries AI after document understanding completed
- **THEN** the stored understanding contract, stable IDs, snapshot, evidence, and coverage are preserved byte-for-byte

#### Scenario: Persisted payload exceeds a fixed bound
- **WHEN** one understanding collection contains more records than its configured contract limit
- **THEN** the collection is deterministically truncated, reports the omitted count, and remains safely serializable
