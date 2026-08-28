## Why

The analyzer should remain useful when AI is disabled by surfacing deterministic document-quality signals that a recruiter can verify in the original CV. Today date ranges are primarily formatted from AI-returned facts, so malformed periods and overlapping employment entries are not independently audited, and the ingestion pipeline does not expose content that is technically present but visually hidden or nearly invisible.

## What Changes

- Add a deterministic timeline audit that parses supported date ranges directly from extracted PDF/DOCX content.
- Report invalid or contradictory periods, normalized durations, and overlapping periods with exact page/line evidence and an explicit distinction between definite and precision-limited possible overlap.
- Add a PDF/DOCX visibility audit for hidden or very-low-visibility text, including format-native hidden flags and conservative style/geometry heuristics.
- Expose both audits as reviewer-facing report data and concise UI findings with expandable evidence; keep the original document as the verification source.
- Keep structural audits outside the deterministic location score, band, automated decision path, and AI input contract. Structural findings are review prompts, not fraud or authenticity verdicts, and remain distinct from existing AI timeline findings.
- Bound stored output and avoid persisting raw hidden-content payloads beyond the evidence needed to locate and verify a finding.

## Capabilities

### New Capabilities

- `cv-structural-audits`: Deterministic timeline consistency and hidden/low-visibility content audits for supported CV files, including report serialization and reviewer presentation.

### Modified Capabilities

<!-- No existing requirement is replaced; this change adds a new, independent audit capability. -->

## Impact

- Backend ingestion adapters for PDF and DOCX, deterministic extraction, report/domain serialization, persistence, and API responses.
- Recruiter-facing analysis results, findings, evidence disclosures, and localized copy in the web app.
- New parser/visibility fixtures and regression tests for PDF, DOCX, sparse documents, ambiguous precision, and false-positive boundaries.
- Existing `pdfplumber` and `python-docx` paths may need additional format-level inspection data; V1 explicitly covers extracted PDF page text spans and DOCX body/table runs, while unsupported embedded/document parts report partial coverage. No OCR, online enrichment, new AI call, scoring-weight, or band change is required.
