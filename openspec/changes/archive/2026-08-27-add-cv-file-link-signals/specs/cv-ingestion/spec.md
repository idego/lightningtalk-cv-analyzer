## ADDED Requirements

### Requirement: Preserve bounded file metadata
PDF and DOCX ingestion SHALL extract only a versioned allowlist of standard document metadata needed by file-detail reporting. Raw custom properties, comments, revision content, and unrelated package metadata MUST NOT enter AI input, application logs, or unbounded report fields.

#### Scenario: Supported metadata is extracted
- **WHEN** a PDF or DOCX contains an allowlisted standard metadata field
- **THEN** ingestion preserves its normalized field name, value, source format, and extractor version for file-detail serialization

#### Scenario: Custom properties are present
- **WHEN** a supported document contains arbitrary custom metadata
- **THEN** ingestion ignores those fields unless a later reviewed version explicitly adds them to the allowlist

### Requirement: Preserve actual hyperlink targets
PDF and DOCX ingestion SHALL preserve actual embedded hyperlink targets and their available display/source mapping separately from URL-shaped visible text. Hyperlink extraction failure MUST NOT discard otherwise usable text, and an invalid link target MUST be retained as a non-requested inspection input rather than dereferenced during ingestion.

#### Scenario: DOCX relationship contains a hyperlink
- **WHEN** a DOCX text run, paragraph, table cell, header, or footer contains an external hyperlink relationship supported by the extractor
- **THEN** ingestion retains its target and available display/source association

#### Scenario: PDF page contains a link annotation
- **WHEN** a PDF page contains a supported URI link annotation
- **THEN** ingestion retains its target, page association, and available displayed text association

#### Scenario: Hyperlink parsing fails
- **WHEN** one embedded hyperlink cannot be parsed safely
- **THEN** ingestion records a bounded invalid-link observation and continues processing usable document text and other links
