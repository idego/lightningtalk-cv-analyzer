## MODIFIED Requirements

### Requirement: Reject unsupported and non-extractable inputs
The system SHALL reject inputs it cannot reliably process and MUST NOT treat extraction failure as a valid empty CV. It SHALL apply a conservative, configurable document-level text-sufficiency policy that distinguishes clearly unusable extraction from a sparse but legitimate CV. The default `minimum_meaningful_tokens` threshold SHALL be 5 across the whole document and MUST NOT be applied per page. After Unicode and whitespace normalization, a meaningful token SHALL contain at least two characters after surrounding punctuation is removed and at least one Unicode letter. Page separators, whitespace, punctuation-only fragments, and isolated one-character extraction artifacts SHALL NOT count.

#### Scenario: Scanned/image-only PDF
- **WHEN** a PDF has no usable extractable text layer
- **THEN** the system rejects it with an error indicating OCR is not supported

#### Scenario: Unsupported format
- **WHEN** a file is neither PDF nor DOCX
- **THEN** the system rejects it with an unsupported-format error

#### Scenario: Empty or extraction-failed file
- **WHEN** a file yields no extractable text or extraction fails
- **THEN** the system returns an extraction error rather than an analysis report

#### Scenario: Clearly insufficient extracted text
- **WHEN** the whole document contains between one and four meaningful tokens with the default configuration
- **THEN** the system returns a distinct insufficient-text error rather than sending the document to deterministic or AI analysis

#### Scenario: Sparse legitimate CV
- **WHEN** a short document contains at least five meaningful tokens with the default configuration
- **THEN** ingestion accepts it and leaves evidence sufficiency to deterministic gray handling and AI unknown states

#### Scenario: Non-meaningful extraction artifacts
- **WHEN** extracted content consists only of page separators, whitespace, punctuation-only fragments, or isolated one-character artifacts
- **THEN** those fragments do not satisfy the text-sufficiency threshold

### Requirement: Preserve positional structure for downstream extraction
The system SHALL use a page model as the canonical ingestion source and SHALL keep stable page IDs, per-page source text, line order, and enough source mapping to validate exact evidence excerpts. During Slice 1 only, it SHALL derive `lines`, `contact_region`, and `body_region` as compatibility views so the existing deterministic pipeline remains behaviorally unchanged. New code MUST NOT depend on those views, and Slice 2 SHALL remove them after migrating legacy consumers. Deterministic extraction and AI analysis SHALL use the canonical source data without inventing headings, tables, columns, regions, or relationships.

#### Scenario: Source order retained
- **WHEN** the system extracts text from a CV
- **THEN** it preserves the source line order and page association

#### Scenario: Header region retained
- **WHEN** leading contact details are explicitly detectable from source position or labels
- **THEN** the system records those candidates with their source positions without requiring a guessed contact/body split

#### Scenario: Page boundaries retained
- **WHEN** the system extracts a multi-page PDF
- **THEN** each real PDF page boundary is preserved and downstream analysis can map each returned fact or finding to its source page

#### Scenario: DOCX has explicit page breaks
- **WHEN** a DOCX contains explicit author-defined page-break constructs
- **THEN** ingestion creates logical pages at only those explicit boundaries

#### Scenario: DOCX has no explicit page breaks
- **WHEN** a DOCX contains no explicit author-defined page break
- **THEN** ingestion represents the document as one logical page

#### Scenario: DOCX rendered layout is unavailable
- **WHEN** Word could paginate a DOCX differently based on fonts, printer settings, or rendering environment
- **THEN** the backend does not guess rendered page boundaries, use inferred rendered-page markers, convert the document to PDF, or call a rendering service

#### Scenario: Compatibility views used by legacy pipeline
- **WHEN** existing Slice 1 deterministic code reads `lines`, `contact_region`, or `body_region`
- **THEN** it receives views derived from the canonical page model and produces the same deterministic report as before the migration

#### Scenario: New code consumes ingestion data
- **WHEN** Slice 1 or later code needs document text or source evidence
- **THEN** it consumes the canonical page model or explicit source-mapped candidates rather than adding a dependency on compatibility views

#### Scenario: Explicit contact candidate retained
- **WHEN** code detects a phone, email, URL, or explicitly labelled location candidate
- **THEN** it records the candidate with exact source evidence without treating a guessed contact region as document truth

#### Scenario: Minimal Markdown prepared
- **WHEN** the system prepares text for AI analysis
- **THEN** it adds stable page separators without guessing headings, tables, columns, regions, or relationships
