## Context

The prototype brief defines the key product invariant as one canonical candidate state: edits must be exactly what preview and export use. CV Analyzer already ingests PDF/DOCX and redacts national IDs before AI processing. Profile Builder should reuse those lower-level capabilities while remaining a sibling workflow to Analyze.

## Goals / Non-Goals

**Goals:**
- Dedicated `CandidateProfile v1` contract with stable IDs on repeated editor sections.
- Dedicated strict OpenAI extraction request over the redacted canonical document.
- Local, immediate editor state with deterministic derived preview/anonymization.
- Snapshot-based editable DOCX export using one hard-coded IDEGO template.
- Regression tests for stale state and anonymization.

**Non-goals:**
- Saving/reopening profiles, team permissions, template persistence, PDF conversion, template designer, OCR, translation, rewriting assistant, batch generation, ATS integrations.

## Decisions

### D1: Profile Builder owns a separate domain contract

The existing AI analysis response is review-oriented and does not contain enough reconstruction detail. Profile Builder keeps its Pydantic profile/anonymization/rendering models together in one substantial `cv_validator/profile_builder.py` module. The existing `ai/request.py`, `ai/application.py`, `ai/openai_client.py`, and `ai/domain.py` are extended for the new structured extraction path rather than creating a parallel AI package. Model output omits UI IDs; code materializes stable per-section IDs after schema validation.

### D2: Extract only from the redacted canonical document

The endpoint reuses `ingest_cv()` and `redact_national_ids()` before creating a dedicated structured-output request. The prompt requires source-faithful extraction, null/empty values for missing facts, and no anonymization during extraction. The existing user-controlled AI setting is forwarded through the web proxy and enforced by the backend so disabling AI also disables Profile Builder model calls.

### D3: Keep one canonical client profile

One cohesive React workspace stores one `profile` object and one `anonymization` policy; field helpers stay local to that workspace instead of being split into many tiny components. The editor mutates only that canonical object. Preview applies anonymization as a pure derived projection. Export POSTs the exact current profile plus policy; it never relies on autosave or a profile ID.

### D4: Use `python-docx` for the first renderer

`python-docx` is already a project dependency and produces semantically editable Word documents. The prototype uses one constrained IDEGO-style flow template rather than introducing a new template engine before the workflow itself is validated.

### D5: Keep persistence and PDF outside the first slice

The profile exists only in browser memory. PDF can later be generated from the same DOCX through LibreOffice, and a constrained visual template system can be added after DOCX correctness is proven.
