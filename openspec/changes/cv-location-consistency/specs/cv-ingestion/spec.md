## ADDED Requirements

### Requirement: Accept supported CV file formats
The system SHALL accept CV files in PDF and DOCX formats and extract their plain text content for downstream analysis.

#### Scenario: Text-extractable PDF
- **WHEN** a PDF whose text layer can be extracted is submitted
- **THEN** the system extracts the plain text and passes it to analysis

#### Scenario: DOCX file
- **WHEN** a DOCX file is submitted
- **THEN** the system extracts the plain text and passes it to analysis

### Requirement: Reject unsupported and non-extractable inputs
The system SHALL reject inputs it cannot reliably process and MUST NOT treat extraction failure as a valid empty CV.

#### Scenario: Scanned/image-only PDF
- **WHEN** a PDF with no extractable text layer (scanned image) is submitted
- **THEN** the system rejects it with an error indicating OCR is not supported

#### Scenario: Unsupported format
- **WHEN** a file that is neither PDF nor DOCX is submitted
- **THEN** the system rejects it with an unsupported-format error

#### Scenario: Empty or extraction-failed file
- **WHEN** a file yields no extractable text
- **THEN** the system returns an extraction error rather than a consistency report

### Requirement: Preserve positional structure for downstream extraction
The system SHALL preserve enough document structure (line order, header/contact region) for the extraction stage to distinguish the contact block from the body.

#### Scenario: Header region retained
- **WHEN** text is extracted from a CV
- **THEN** the leading contact/header region is identifiable as distinct from later body sections
