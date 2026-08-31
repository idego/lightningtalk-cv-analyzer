## Why

The analyzer already performs substantial deterministic ingestion, candidate extraction, location resolution, structural auditing, and AI evidence validation, but these paths re-read the same document and do not share section, date-range, entry, or research-subject annotations. As a result, AI can remain the only source of education and employment records, so a valid CV section can disappear from downstream research when one model response omits it.

This change consolidates the existing code-owned capabilities into one architecture-preserving document-understanding pass. It improves repeatability and coverage without rewriting the ingestion, scoring, persistence, or API architecture and without moving AI into the verdict path.

## What Changes

- Add one internal `DocumentUnderstandingResult` built over the existing redacted canonical document and deterministic result types.
- Add one versioned annotation index for section spans, date spans/ranges, entry boundaries, structured fields, confidence, and exact source evidence.
- Quarantine values sourced exclusively from exact-mapped hidden or strongly low-visibility spans before structured facts, research subjects, or verdict candidates are materialized. This intentionally fixes the existing case where hidden text can influence scoring; ordinary visible-input scoring remains invariant.
- Detect the standard CV section catalog deterministically, while retaining unsupported or uncertain headings as bounded unknown sections instead of guessing.
- Build code-owned structured entries for education, employment, and explicitly listed skills using one shared section-and-entry mechanism rather than independent category parsers.
- Reuse the shared section and date annotations when projecting the existing structural-audit contract, eliminating duplicate date and heading interpretation without changing its public payload.
- Derive bounded company and education research subjects from accepted code-owned entries plus independently validated AI additions. AI failure or omission cannot delete a code-owned subject.
- Provide code-owned sections, entries, ambiguous blocks, and missing fields as context for AI enrichment while preserving field-level source validation and deterministic scoring exclusion.
- Keep `pdfplumber` and `python-docx` as production adapters and keep Docling, Unstructured, PyMuPDF, pretrained models, and OCR outside this implementation.
- Use the existing Python runtime behind a replaceable matcher boundary and only local, versioned reference data for explicit skill matching. A reviewed ESCO snapshot is the V1 taxonomy input; runtime taxonomy lookup makes no network request. spaCy and O*NET remain separate future adoption decisions.
- Consolidate shared normalization and date handling. Fuzzy matching and multilingual date parsing remain bounded helpers for already identified spans and cannot independently create facts.
- Preserve existing API shapes, persistence readability, structural-audit contract, deterministic score/band behavior, national-ID redaction, source IDs, and report reopening behavior.
- Add a bounded, sanitized, retry-stable top-level understanding payload and a dual-read migration in which new reports prefer code-owned records while legacy reports continue to use retained AI facts.

## Capabilities

### New Capabilities

- `document-understanding`: Defines the single code-owned annotation and structured-entry pass, its evidence/confidence rules, supported section catalog, deterministic education/employment/skills coverage, compatibility projections, reference-data boundaries, and failure behavior.

### Modified Capabilities

- `cv-ingestion`: Extends the canonical redacted document with reusable source-mapped block/presentation structure while keeping current PDF/DOCX adapters and compatibility behavior.
- `ai-document-analysis`: Supplies code-owned understanding context to AI, reconciles validated additions without letting AI remove code-owned entries, and keeps all AI output outside scoring.
- `ai-assisted-research`: Builds research requests from the combined validated subject projection so education and company research do not depend solely on one AI response.
- `location-analysis-api`: Adds the exact bounded `document-understanding-v1` report contract and legacy-null behavior.
- `frontend-analysis-workflow`: Adds dual-read rendering and stable new-report record relationships while preserving legacy AI fallback.
- `location-signal-extraction`: Applies exact hidden-source quarantine consistently before existing deterministic candidate/fact materialization.
- `consistency-scoring`: Preserves all visible-source verdict inputs while excluding values supported exclusively by exact quarantined hidden spans.
- `cv-structural-audits`: Reuses shared section/date annotations while preserving the byte-compatible `structural-audits-v1` payload; record mapping lives in document understanding.

## Impact

- Primary code areas: `ingestion/`, `extraction/`, `structural/`, `pipeline.py`, `ai/request.py`, `ai/validation.py`, `research/company.py`, and `research/education.py`.
- Existing `RedactedDocument`, `Candidate`, `Fact`, `Observation`, `ScoringSignal`, `DeterministicAnalysisResult`, `StructuralAuditResult`, and report serializers remain the compatibility foundation.
- New internal types and rule/reference manifests are added without replacing current public report contracts.
- The current production container does not gain Docling, PyTorch, OCR, Unstructured, PyMuPDF, a new service, or runtime reference-data downloads in this change.
- No new parsing or NLP runtime dependency is required by this change. Any later dependency requires an explicit size/startup benchmark, compatible license review, pinned version, offline behavior, and a separate reviewed change. PyMuPDF remains out of scope absent an approved AGPL/commercial licensing decision.
- Private CV evaluation data remains ignored and untracked; committed fixtures must be synthetic or anonymous and contain no candidate PII.
