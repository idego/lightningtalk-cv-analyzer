## Why

Candidates frequently state a location on their CV that does not match the circumstantial evidence in the same document, creating problems for remote-work anti-fraud, right-to-work/sanctions/tax screening, and basic CV data-quality. We have no automated way to surface these mismatches today, so recruiters either miss them or spot-check manually and inconsistently.

A batch CV file contains no signal that can *prove* where a person physically sits, so this change deliberately scopes to **consistency analysis as decision support** — never automated verification or rejection.

## What Changes

- Introduce a Python library that takes a CV (PDF/DOCX, text-extractable, English-primary) and returns a structured location-consistency report.
- Parse the **claimed** location from the CV body (header/contact block) and test it against independent in-CV evidence: phone country code, contact-block address/postal format, most-recent-employer location, date-format convention, spelling locale, education locations, currency, email TLD, right-to-work/visa statements, and national-ID presence.
- Score signals with a **config-driven weighted sum** producing a 0–100 score and one of four bands: green, amber, red, and **gray (insufficient evidence)**.
- Emit an itemized, explainable report (per-signal observed vs claimed, agreement direction, weight, rationale) plus a plain-language summary; **human-in-the-loop, never auto-reject**.
- Run all enrichment **offline** (libphonenumber phone→country, static TLD→country table) — no third-party PII exposure.
- Expose the core via a **FastAPI service** with single-CV upload and batch endpoints, JSON output.
- Persist minimal data with a full **audit trail** (input hash + ruleset/weights version + output); national IDs stored as `present/type` only, never raw value.

## Capabilities

### New Capabilities
- `cv-ingestion`: Accept and validate PDF/DOCX uploads, extract plain text, reject unsupported/scanned/non-text inputs.
- `location-signal-extraction`: Identify the claimed location and extract all location-bearing evidence signals from CV text using a gazetteer and positional/pattern rules (no ML/LLM).
- `consistency-scoring`: Aggregate weighted signal votes into a 0–100 score and four-band classification, producing an explainable, reproducible report.
- `location-analysis-api`: FastAPI service exposing single and batch analysis endpoints, with minimal-retention persistence, ruleset versioning, and an immutable audit log.

### Modified Capabilities
<!-- None. Greenfield project; no existing specs. -->

## Impact

- **New codebase** (greenfield): Python library core + FastAPI service.
- **Dependencies**: `phonenumbers` (offline libphonenumber), PDF text extraction (`pdfplumber`/PyMuPDF), `python-docx`, a GeoNames-style gazetteer dataset, FastAPI + Uvicorn.
- **Data/legal**: minimal retention, configurable window, immutable audit log, national-ID redaction; outputs stamped "decision-support, not automated rejection."
- **Out of scope (deferred)**: OCR/scanned CVs, non-English CVs, live online enrichment (MX/address APIs), structured-field claim source, ATS connector.
