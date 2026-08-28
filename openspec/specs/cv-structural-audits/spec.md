# cv-structural-audits Specification

## Purpose
Provides deterministic, evidence-first audits for CV timeline consistency and technically present but hidden or barely visible document content, so recruiters can review useful signals even when AI analysis is unavailable.

## Requirements

### Requirement: Use a versioned structural-audit contract

Every new analysis report SHALL contain a top-level `structural_audits` object, or `null` only when reading a legacy report created before this capability existed. The object SHALL use contract version `structural-audits-v1` and SHALL have exactly these top-level fields: `contract_version`, `status`, `snapshot_month`, `coverage`, `timeline`, and `visibility`. `status` SHALL be one of `completed`, `partial`, `unavailable`, or `not_applicable`; section statuses SHALL use the same values. `completed` means every present in-scope surface was inspected without a cap or inspection error, `partial` means at least one present/required surface was omitted, capped, or only partly mapped, `unavailable` means an applicable inspection could not start or return a usable result, and `not_applicable` means the input has no such inspection surface. `snapshot_month` SHALL be `YYYY-MM` for a new analysis and SHALL be the month used to resolve open-ended ranges.

The `coverage` object SHALL contain `status`, `source_format`, `audited_parts`, and `omitted_parts`. Its status SHALL use the same four values and meanings as the top-level status. V1 audited parts are `pdf_page_text_spans` for PDF, `docx_body_paragraph_runs`, `docx_table_cell_runs`, and `docx_logical_page_breaks` for DOCX, and `plain_text_pages` for text input. Detected but unsupported PDF image/OCR/non-text content and DOCX headers, footers, textboxes, footnotes/endnotes, comments, drawings, and embedded files SHALL be listed in `omitted_parts`; a no-finding result SHALL be `partial` when such content is present or an in-scope part was not inspected.

The `timeline` object SHALL contain `status`, `parser_version`, `entries`, `summaries`, `observations`, `reported_entry_count`, `additional_entry_count`, and `truncated`. The `visibility` object SHALL contain `status`, `detector_version`, `threshold_version`, `observations`, `reported_observation_count`, `additional_observation_count`, and `truncated`. `timeline.entries` SHALL contain at most 100 entries, `timeline.observations` at most 100 observations, and `visibility.observations` at most 50 observations per file. All reported arrays SHALL be ordered by source position; timeline observations SHALL order invalid entries before overlap pairs, and visibility observations SHALL order by page/source position and then trigger code. Counts SHALL include omitted items when truncation occurs.

Every source location SHALL contain `page_id`, positive `page_number`, nullable `line_id`, nullable `line_number`, nullable `start_offset`, nullable `end_offset`, nullable `paragraph_path`, nullable `bbox`, and `association`. `association` SHALL be `exact`, `partial`, or `unmapped`; offsets SHALL be present only for an exact or partial canonical mapping, and `bbox` SHALL contain finite `x0`, `y0`, `x1`, and `y1` values with `x0 <= x1` and `y0 <= y1`. Timeline evidence MAY contain a source excerpt of at most 256 characters. Visibility observations MUST NOT contain raw text or an `excerpt` field; they MAY contain only source location, trigger codes, confidence, bounded counts, redaction metadata, and threshold/version data.

The nested records SHALL use these exact fields and nullability rules:

```text
TimelineEntry = {
  id: string,
  category: employment | education | unknown,
  status: valid | invalid | unresolved,
  start_text: string | null,
  end_text: string | null,
  start_month: YYYY-MM | null,
  end_month: YYYY-MM | null,
  start_precision: month | year | open_ended | unknown,
  end_precision: month | year | open_ended | unknown,
  source_location: SourceLocation,
  evidence: TimelineEvidence[]
}

TimelineSummary = {
  category: employment | education | unknown,
  entry_count: integer >= 0,
  earliest_month: YYYY-MM | null,
  latest_month: YYYY-MM | null,
  non_overlapping_months: integer >= 0
}

TimelineObservation = {
  id: string,
  kind: invalid_period | definite_overlap | possible_overlap,
  status: needs_review | informational,
  entry_ids: string[],
  overlap_months: integer >= 1 | null,
  precision: exact | coarse | null,
  reason_code: string,
  evidence: TimelineEvidence[]
}

VisibilityObservation = {
  id: string,
  kind: hidden_text | near_zero_text | zero_opacity_text | low_contrast_text,
  status: needs_review,
  confidence: high | medium,
  source_location: SourceLocation,
  trigger_codes: string[],
  character_count: integer >= 0,
  word_count: integer >= 0,
  redaction: { present: boolean, type_hints: string[] } | null,
  threshold_version: string
}

TimelineEvidence = { location: SourceLocation, excerpt: string }
```

`TimelineObservation.entry_ids` SHALL contain one ID for an invalid period and exactly two IDs for an overlap. `start_text`, `end_text`, reason codes, and trigger codes SHALL each be bounded to 64 characters, and `trigger_codes` SHALL contain at most four values. V1 timeline reason codes are `invalid_month`, `start_after_end`, `definite_calendar_overlap`, and `possible_calendar_overlap`; V1 visibility trigger codes are `explicit_hidden`, `near_zero_font`, `zero_opacity`, `low_contrast`, and `redacted_sensitive_span`. `VisibilityObservation` has no raw source-text field. All IDs, codes, strings, and arrays are bounded by the limits declared in this requirement and the versioned configuration.

#### Scenario: New report exposes the complete contract

- **WHEN** a new supported CV is analyzed
- **THEN** `structural_audits` contains both timeline and visibility sections with the required fields, statuses, versions, counts, coverage, and snapshot month
- **AND** the field values are JSON-safe and machine-readable independently of UI language

#### Scenario: Legacy report is reopened

- **WHEN** a report created before structural audits is loaded
- **THEN** its missing structural-audit field is treated as `null`
- **AND** the frontend does not infer that an audit completed or that no anomaly was found

#### Scenario: Audit output reaches a configured limit

- **WHEN** a file contains more entries or observations than the configured per-file limit
- **THEN** the corresponding array is deterministically truncated, `truncated` is `true`, and `additional_entry_count` or `additional_observation_count` reports the omitted count
- **AND** the result remains valid without serializing unbounded source data

#### Scenario: Unsupported document parts are present

- **WHEN** a DOCX contains text in a header or a PDF contains non-text content outside the audited text-span surface
- **THEN** the relevant part is listed in `coverage.omitted_parts` and the audit status is `partial` rather than a misleading completed no-finding result

#### Scenario: AI retry preserves the structural snapshot

- **WHEN** an analysis with an open-ended period is persisted and its AI section is later replaced by a retry
- **THEN** the retry response preserves the original `snapshot_month`, timeline entries, observations, coverage, and visibility result byte-for-byte
- **AND** it does not recompute structural audits from a later wall-clock month

### Requirement: Parse timeline ranges from source content without AI

The system SHALL parse supported date ranges directly from the canonical extracted pages of a CV, independently of AI analysis. Each valid or invalid range SHALL include its normalized start/end when available, endpoint precision, timeline category (`employment`, `education`, or `unknown`), and source evidence whose association is `exact` or `partial`; an unresolved range MAY use `unmapped` source association but cannot produce an anomaly claim. The supported date grammar SHALL be versioned and SHALL cover numeric month/year values, four-digit years, supported English and Polish month names and abbreviations, and open-ended `present`/`current`/`now` values. A broad date-like lexer SHALL retain malformed numeric month/year candidates, such as `13/2024`, for validation rather than discarding them as non-matches. The parser MUST NOT invent missing months, roles, employers, or category relationships.

V1 SHALL associate a range with an entry only when the range and entry text occur on the same canonical source line under a recognized employment or education heading. A new recognized top-level heading SHALL reset the section state; headings classified as other (including contact, birth details, certifications, projects, publications, and awards) SHALL not produce employment or education entries. The parser MUST NOT join ranges across lines, infer visual columns, or treat an isolated header/contact date as an employment or education entry. Unsupported or unclassified ranges remain `unknown` or unresolved for disclosure and are excluded from anomaly pairing.

#### Scenario: AI is disabled but timeline ranges are present

- **WHEN** a text-extractable CV contains supported employment or education ranges and AI analysis is disabled
- **THEN** the system produces deterministic timeline entries from the source pages
- **AND** the entries include source evidence and do not depend on an AI fact payload

#### Scenario: Localized month name is supported

- **WHEN** a CV contains a supported English or Polish month name in a date range
- **THEN** the system normalizes the month without changing the source excerpt
- **AND** records the parser version used for that normalization

#### Scenario: Date-like text cannot be safely classified

- **WHEN** a date-like expression has unsupported syntax or cannot be associated with an employment or education entry without guessing
- **THEN** the system retains it as an unresolved or unparseable timeline observation with source evidence
- **AND** does not use it to create an overlap or duration claim

#### Scenario: Malformed date-like token is retained for validation

- **WHEN** a source line in a recognized timeline section contains `13/2024 - 02/2025`
- **THEN** the date-like lexer retains the range and the validator reports the invalid month
- **AND** the parser does not silently treat the token as ordinary text

#### Scenario: Unrelated date is outside the timeline surface

- **WHEN** a contact or certification section contains a birth date or certificate date
- **THEN** the system does not classify it as an employment or education entry
- **AND** it cannot create a timeline overlap or duration total

#### Scenario: Timeline evidence is returned to the reviewer

- **WHEN** a timeline entry is included in an analysis report
- **THEN** the report identifies its page, line or source location, normalized period, precision, and bounded original date evidence

### Requirement: Validate periods and calculate deterministic month durations

The system SHALL validate every parsed period before using it in duration or overlap calculations. A period with an invalid calendar component or a start after its end SHALL be reported as an `invalid_period` observation and SHALL NOT contribute to a duration or overlap calculation. Valid periods SHALL use inclusive calendar-month intervals for display and complete-month calculations; a year-only endpoint SHALL cover the referenced calendar year, and an open-ended endpoint SHALL resolve to the analysis run month recorded in the report. The system SHALL provide merged non-overlapping duration totals per timeline category when at least one valid range in that category is available.

#### Scenario: Start is later than end

- **WHEN** a parsed range has a start month after its end month
- **THEN** the report shows an `invalid_period` observation with both source endpoints and the exact source evidence
- **AND** the invalid range is excluded from duration and overlap totals

#### Scenario: Month value is outside the calendar

- **WHEN** a date range contains a month value outside 1 through 12
- **THEN** the report marks the range invalid rather than normalizing or silently dropping it
- **AND** the original date evidence remains available for human review

#### Scenario: Open-ended employment is valid

- **WHEN** a supported range ends in `present`, `current`, or `now`
- **THEN** the system treats the analysis run month as the inclusive end month
- **AND** records that snapshot month so the result is reproducible for that run

#### Scenario: Future period is not automatically impossible

- **WHEN** a syntactically valid period extends beyond the analysis run month
- **THEN** the system does not label it fraudulent or impossible solely because it is future-dated
- **AND** leaves the period available as a neutral review item or valid timeline data according to its other properties

### Requirement: Detect precision-aware overlapping periods

The system SHALL compare valid periods only within the same deterministically classified timeline category and SHALL report each distinct pair at most once. When both periods have month-precise endpoints and share one or more complete calendar months, the report SHALL create a `definite_overlap` observation containing the shared-month count. When one or both periods are year-precision or mixed-precision and their coarse intervals intersect, the report SHALL create a `possible_overlap` observation, SHALL identify the limited precision, and MUST NOT present an exact shared-month count as fact. Periods that merely meet at adjacent calendar-month boundaries SHALL NOT overlap. Overlap observations SHALL be neutral review prompts and SHALL NOT be treated as proof of inconsistency, misconduct, fraud, or deception.

#### Scenario: Exact month ranges overlap

- **WHEN** two employment ranges with month-precise endpoints share three complete calendar months
- **THEN** the report shows one `definite_overlap` observation for the pair with an overlap duration of three months
- **AND** includes source evidence for both periods

#### Scenario: Year-only ranges may overlap

- **WHEN** two education or employment ranges intersect only at year-level precision
- **THEN** the report shows a `possible_overlap` observation with a precision limitation
- **AND** does not claim an exact overlap duration

#### Scenario: Employment and education coexist

- **WHEN** an employment period overlaps an education period
- **THEN** the system does not report that cross-category pairing as an impossible timeline
- **AND** it may retain both periods in their separate category summaries

#### Scenario: Concurrent work is possible

- **WHEN** two employment periods overlap
- **THEN** the report describes the temporal overlap and asks for human review of the arrangement
- **AND** does not infer that either entry is false or mutually exclusive

### Requirement: Detect hidden and low-visibility document content conservatively

For PDF and DOCX inputs, the system SHALL inspect available format-level text presentation properties only within the V1 audited surface declared by `coverage` and SHALL report bounded visibility observations when content is technically present but explicitly hidden or rendered with a strong low-visibility signal. Supported signal types SHALL include format-native hidden text, zero or near-zero rendered text size, zero or near-zero opacity where available, and near-white text on a deterministically known light background. Size and contrast thresholds SHALL be format-normalized, versioned, and configurable; a literal pixel threshold from one format MUST NOT be applied as a universal rule to another. The audit MUST NOT require OCR, external services, rendering services, or AI.

#### Scenario: DOCX contains explicitly hidden text

- **WHEN** a DOCX text run has a format-native hidden or vanished-text property
- **THEN** the audit reports a high-confidence hidden-content observation with its document location and trigger type
- **AND** the analysis continues normally

#### Scenario: PDF contains near-zero text

- **WHEN** a PDF text span has a rendered size at or below the configured near-zero threshold and contains meaningful text
- **THEN** the audit reports a low-visibility observation with the page location, bounded geometry, character or word count, and applied threshold version
- **AND** it does not call the content fraudulent or malicious

#### Scenario: White text is on a known light background

- **WHEN** a PDF or DOCX text span is white or near-white and the surrounding background is deterministically known to be white or light
- **THEN** the audit reports a low-contrast visibility observation with the measured or normalized trigger data
- **AND** does not expose the full hidden text as part of the finding

#### Scenario: White text background is unknown

- **WHEN** text is white or near-white but the document does not provide enough background information to establish low contrast
- **THEN** the audit does not label the text hidden solely from its foreground color
- **AND** records the visibility audit as unable to evaluate that signal where appropriate

#### Scenario: Legitimate light-on-dark design is present

- **WHEN** white text is rendered over a deterministically identified dark background
- **THEN** the system does not report it as hidden or low visibility

#### Scenario: Redacted national-ID span is the only hidden content

- **WHEN** a hidden or low-visibility presentation span overlaps a mandatory national-ID redaction and contains no remaining alphanumeric characters
- **THEN** the audit retains only safe presence/type, source-location, trigger, and bounded-count metadata for that span
- **AND** the meaningful-content filter does not erase the fact that the redacted sensitive span was inspected

#### Scenario: Inherited presentation value is unknown

- **WHEN** a DOCX run inherits a color, size, or shading value that cannot be resolved safely from the supported styles
- **THEN** the corresponding visibility rule reports no positive finding from that unknown value
- **AND** the visibility coverage records the affected inspection as partial or unavailable where appropriate

### Requirement: Return structural audits as independent reviewer data

The analysis report SHALL include the versioned `structural_audits` result for every new analysis. Timeline parsing SHALL operate on the canonical text surface; visibility inspection SHALL operate only on the V1 PDF page-text-span or DOCX body/table-run surface declared in `coverage`. An unavailable or partially inspectable format-level visibility inspection SHALL produce the corresponding neutral `unavailable` or `partial` state and MUST NOT fail an otherwise usable CV analysis. A `completed` visibility state means all present in-scope text spans were inspected; it does not claim that omitted images, headers, footers, textboxes, footnotes, comments, drawings, or embedded content were inspected. The API and persisted report SHALL preserve the same bounded audit data used by the dedicated UI component.

#### Scenario: No structural anomaly is found

- **WHEN** the timeline and visibility audits complete without findings
- **THEN** the report records successful audit completion and does not add an alarming candidate flag
- **AND** the recruiter can distinguish “no finding” from “audit unavailable”

#### Scenario: Visibility inspection is unavailable

- **WHEN** a supported file can be text-extracted but its presentation attributes cannot be inspected safely
- **THEN** the report keeps the base deterministic analysis and marks only the visibility audit unavailable
- **AND** it does not imply that hidden content is absent

#### Scenario: Report is persisted and reopened

- **WHEN** a completed report containing structural audits is saved and later loaded
- **THEN** the API returns the same audit statuses, normalized periods, observations, source locations, and extractor versions
- **AND** no new AI call is needed to reconstruct the audit

#### Scenario: Timeline-only input is analyzed

- **WHEN** a plain text analysis input has canonical pages but no PDF or DOCX presentation data
- **THEN** the timeline section may complete and the visibility section is `not_applicable`
- **AND** the overall coverage does not imply that format-level visibility was checked

### Requirement: Present structural findings with an explicit review boundary

The recruiter UI SHALL render structural audits in a dedicated, typed structural-review component rather than passing them through the existing generic `ReviewFlag`/fixed checklist renderer. It SHALL show invalid periods, definite overlaps, possible overlaps, and hidden/low-visibility observations as concise structural-review items with expandable safe evidence. The UI SHALL label precision-limited overlaps as possible, label visibility items as needing review, show partial/unavailable coverage, and keep raw hidden-content text omitted or safely redacted. Structural audit items MUST NOT use the `SUSPICIOUS` state, a fraud/authenticity claim, or a candidate-level verdict, and they MUST NOT add an unrecognized ID to the existing fixed checklist records.

#### Scenario: Recruiter reviews an exact overlap

- **WHEN** a report contains a definite overlap
- **THEN** the UI shows the two affected periods, shared-month count, and a neutral human-review explanation
- **AND** the evidence disclosure links both source locations

#### Scenario: Recruiter reviews a hidden-content observation

- **WHEN** a report contains a hidden or low-visibility observation
- **THEN** the UI shows a `Needs review` structural item with its signal type, page or source location, and bounded technical details
- **AND** keeps the hidden text itself omitted or redacted so the original document remains the verification source

#### Scenario: Polish UI is selected

- **WHEN** the recruiter uses the Polish UI language
- **THEN** structural audit labels, statuses, explanations, and review actions are localized in Polish
- **AND** the underlying machine-readable observation codes remain stable

#### Scenario: Structural item reaches the UI renderer

- **WHEN** a report contains a visibility observation without a text excerpt
- **THEN** the dedicated structural component renders its safe location and trigger metadata without assuming an `excerpt` field
- **AND** the existing generic finding renderer and fixed checklist labels are not used for that item

### Requirement: Keep structural audits outside verdict and enrichment paths

Structural audit observations SHALL be deterministic, evidence-first, and independent of AI availability. They MUST NOT change the configured location score, band, score inputs, scoring signal count, automated action, or research requests. Structural audit findings MUST NOT be sent as instructions or facts to an AI prompt or public research provider. The existing AI input builder and prompt version SHALL not accept the structural-audit object.

#### Scenario: Structural findings coexist with a deterministic score

- **WHEN** a CV produces an invalid period, overlap, or visibility observation
- **THEN** the report exposes the observation for human review
- **AND** the deterministic location score and band remain identical to a run without those observations

#### Scenario: AI is unavailable

- **WHEN** AI analysis is disabled or fails
- **THEN** structural audits still run where their input is available
- **AND** the UI does not replace the audits with an AI-incomplete error

#### Scenario: Research is enabled

- **WHEN** public company, education, or LinkedIn research is enabled for a report
- **THEN** structural audit observations do not become research subjects or query instructions
- **AND** research remains bounded to its existing explicitly supplied inputs

#### Scenario: AI already reports a semantic timeline overlap

- **WHEN** the AI response contains `timeline_overlap` for evidence that also has a deterministic structural overlap
- **THEN** the report preserves the two authorities and their distinct machine-readable codes
- **AND** the UI does not treat the AI finding as confirmation of the deterministic finding or silently replace one with the other

### Requirement: Bound structural audit evidence and protect sensitive content

The system SHALL cap the number and size of structural observations per file, deduplicate repeated source spans and symmetric timeline pairs, and attach extractor/threshold versions to deterministic output. It MUST NOT persist or log raw text in the structural-audit result when that text was identified only as hidden or low-visibility. Structural-audit metadata MUST NOT be sent to AI or research as facts, instructions, or query subjects; the existing redacted CV-input contract remains unchanged. The audit MAY retain a bounded redacted marker, source location, trigger metadata, and counts needed for verification. National-ID redaction rules SHALL continue to apply before any structural audit data enters downstream output or persistence.

#### Scenario: Many repeated hidden spans exist

- **WHEN** a file contains more hidden or low-visibility spans than the configured report limit
- **THEN** the report returns a bounded aggregate with the number of additional spans
- **AND** does not serialize every hidden span or its raw content

#### Scenario: A hidden span contains a national ID

- **WHEN** a hidden or low-visibility span includes a detected national-ID pattern
- **THEN** the structural result contains only allowed presence/type metadata and safe location information
- **AND** no raw identifier or partial identifier is emitted or persisted

#### Scenario: Persistence sanitizes initial save and AI retry

- **WHEN** a report with structural audits is initially saved or its AI section is replaced by retry
- **THEN** the same structural allowlist and sanitizer validate the structural object before it is written to the audit log or returned
- **AND** hidden excerpts, unknown fields, and raw sensitive values are omitted without deleting the safe structural status and locations
