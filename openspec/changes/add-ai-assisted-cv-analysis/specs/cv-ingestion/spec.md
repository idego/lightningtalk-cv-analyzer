## MODIFIED Requirements

### Requirement: Preserve positional structure for downstream extraction
The system SHALL keep page numbers, per-page source text, line order, and the header/contact region. Fixed rules and AI analysis SHALL use this data without inventing document structure.

#### Scenario: Header region retained
- **WHEN** the system extracts text from a CV
- **THEN** it keeps the contact/header region separate from the body

#### Scenario: Page boundaries retained
- **WHEN** the system extracts a multi-page CV
- **THEN** downstream analysis can map each text block to its source page

#### Scenario: Minimal Markdown prepared
- **WHEN** the system prepares text for AI analysis
- **THEN** it adds page separators without guessing headings, tables, columns, or relationships
