## 1. Project Setup

- [x] 1.1 Scaffold Python package (`pyproject.toml`, `src/` layout, package name) with deps: `phonenumbers`, `pdfplumber` (or PyMuPDF), `python-docx`, `fastapi`, `uvicorn`, `pytest`
- [x] 1.2 Define core domain types: `Signal`, `Finding`, `Band` (green/amber/red/gray), `Report`, `RulesetVersion`
- [x] 1.3 Add a `weights.yaml`/`weights.toml` config file with per-signal weights and band thresholds, plus a loader

## 2. CV Ingestion (capability: cv-ingestion)

- [x] 2.1 Implement PDF text extraction; detect and reject scanned/no-text-layer PDFs
- [x] 2.2 Implement DOCX text extraction
- [x] 2.3 Reject unsupported formats and empty/extraction-failed inputs with explicit errors (not empty-CV)
- [x] 2.4 Preserve line order and identify the contact/header region distinct from the body
- [x] 2.5 Tests for each ingestion scenario (text PDF, DOCX, scanned PDF, unsupported, empty)

## 3. Gazetteer & Location Resolution (capability: location-signal-extraction)

- [x] 3.1 Source and load a GeoNames-style gazetteer (countries/regions/cities)
- [x] 3.2 Implement location string → country/region resolution with ambiguity detection (no silent pick)
- [x] 3.3 Tests for unambiguous and ambiguous resolution (e.g. "Paris, TX" vs "Paris, FR")

## 4. Claim Identification (capability: location-signal-extraction)

- [x] 4.1 Identify the claimed location from the contact/header region
- [x] 4.2 Mark claim undetermined when not confidently identifiable
- [x] 4.3 Tests for claim-present and no-claim scenarios

## 5. Signal Extractors (capability: location-signal-extraction)

- [x] 5.1 Phone country code via offline libphonenumber (STRONG)
- [x] 5.2 Contact-block address/postal-code format (STRONG)
- [x] 5.3 Most-recent-employer location, recency-weighted (MEDIUM)
- [x] 5.4 Date-format convention DD/MM vs MM/DD (MEDIUM)
- [x] 5.5 Spelling locale en-US/en-GB (WEAK)
- [x] 5.6 Education locations, currency, email TLD (WEAK)
- [x] 5.7 Right-to-work/visa statement surfacing (finding regardless of weight)
- [x] 5.8 National-ID presence/type detection that never captures the raw value
- [x] 5.9 Tests per extractor, including national-ID redaction assertion

## 6. Scoring Engine (capability: consistency-scoring)

- [x] 6.1 Implement config-driven weighted-sum aggregation of signal votes → 0–100 score
- [x] 6.2 Implement four-band classification; sparse CV → gray (never green); borderline → bias to review
- [x] 6.3 Build the report: score, band, itemized findings (observed/claimed/direction/weight/rationale), plain-language summary
- [x] 6.4 Stamp decision-support disclaimer; ensure no auto-decision path exists
- [x] 6.5 Guarantee determinism: same input + ruleset version → identical report
- [x] 6.6 Tests for agree/conflict/sparse/borderline and reproducibility

## 7. FastAPI Service (capability: location-analysis-api)

- [x] 7.1 Single-CV upload endpoint returning JSON report; error response for rejected uploads
- [x] 7.2 Batch endpoint returning per-CV report with isolated per-file errors
- [x] 7.3 Minimal-retention persistence storing findings + score + ruleset/weights version (national ID as presence/type only)
- [x] 7.4 Immutable audit log: input hash + ruleset version + output
- [x] 7.5 Configurable retention window
- [x] 7.6 API tests: single success, rejected upload, mixed batch, audit-entry written, national-ID not retained

## 8. Calibration & Hardening

- [x] 8.1 Assemble calibration set (real and/or synthetic CVs, including known-mismatched cases)
- [x] 8.2 Calibrate weights so strong-signal conflicts dominate the weak pool; lock production `weights` config
- [x] 8.3 End-to-end smoke test across all four bands
- [x] 8.4 README with usage, scope limits (no OCR/non-English/online enrichment), and the "decision-support, not verification" disclaimer
