## ADDED Requirements

### Requirement: Expose reusable source-mapped document blocks

The canonical ingestion result SHALL expose a bounded, ordered block surface derived by the configured PDF or DOCX adapter for reuse by deterministic understanding. Each block SHALL identify its page, canonical line and offset associations where available, source order, block kind, table/list membership where available, and supported presentation metadata. The block surface SHALL extend the existing page model and MUST NOT change canonical redacted text, stable page and line identifiers, or national-ID masking behavior.

Ingestion SHALL parse the source file through its configured adapter once per analysis request. Downstream structural, link, and semantic projections MUST consume canonical pages, blocks, spans, and annotations rather than reopen or independently traverse the source package. Adapter extraction failure for optional presentation or block metadata SHALL produce partial coverage without discarding otherwise sufficient canonical text.

#### Scenario: DOCX contains paragraphs and tables
- **WHEN** a DOCX body contains ordered paragraphs and table-cell content
- **THEN** ingestion exposes their source order and available structural membership through one reusable canonical block surface

#### Scenario: PDF exposes positioned text
- **WHEN** a text-extractable PDF provides word or line geometry
- **THEN** ingestion retains bounded source-mapped block geometry without changing canonical page and line evidence

#### Scenario: Optional block metadata fails
- **WHEN** text extraction succeeds but optional structural or presentation metadata cannot be associated safely
- **THEN** canonical text remains analyzable and block coverage is partial
- **AND** downstream code does not invent the missing association

#### Scenario: Downstream analysis runs
- **WHEN** structural audit, link association, or document understanding needs source structure
- **THEN** it consumes the reusable canonical surfaces without reopening the submitted PDF or DOCX package
