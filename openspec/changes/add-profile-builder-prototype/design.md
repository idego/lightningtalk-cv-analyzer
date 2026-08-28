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
- Team-shared permissions, PDF conversion, arbitrary absolute-position canvas features, OCR, translation, rewriting assistant, batch generation, ATS integrations.

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


### D6: Persist exact Profile Builder snapshots for Recent

Recent profiles use the existing SQLite persistence layer. A stored record contains the owner-scoped canonical `CandidateProfile`, anonymization policy, exact selected template snapshot, source filename, and created/updated timestamps. The original uploaded PDF/DOCX bytes are never stored. The editor autosaves the current snapshot after a debounce and opening Recent restores that exact state.

### D7: Use a constrained normalized template model

The Template Creator edits a `profile-template-v1` JSON contract rather than raw DOCX/Jinja/pdfme data. V1 supports brand text/accent, font family/sizes, header visibility, ordered domain sections, section titles, visibility, and simple inline/bulleted list presentation. It deliberately excludes arbitrary coordinates, overlap, rotation, and free-form drawing.

The same exact template snapshot is sent with DOCX export, avoiding a save/export race. The browser preview and DOCX renderer both consume the same normalized template contract.

### D8: Keep template management inside the Profile Builder flow

The upload state shows the current template beside Recent profiles. A template manager dialog can select a template, create a new one, or navigate to editing an existing one. `/profile-builder/templates/new` and `/profile-builder/templates/<id>` render the same Template Creator screen. The built-in `idego-default` can be owner-customized without changing other users; deleting that override falls back to the built-in default.


### D9: Keep AI Summary cheap and source-faithful

AI Summary uses the existing pinned `gpt-5.6-luna` model with `reasoning.effort = none`, no tools, response storage disabled, and a 384-token output ceiling. The request excludes personal/contact data and the existing Summary so regeneration is grounded in professional profile facts rather than its own previous output. Recruiter instructions or pasted job descriptions may steer focus, tone, or language but are explicitly not a source of candidate facts. The returned text replaces the one canonical `profile.summary` value and therefore flows through autosave, preview, and export automatically.

### D10: Allow one constrained free-position logo element

The document flow remains constrained to semantic profile blocks. The only V1 free-positioned canvas element is an optional company logo. HR may upload PNG, JPG, WebP, or SVG; the browser sanitizes SVG network/script content and normalizes every upload to bounded PNG data stored in the template snapshot. Position and width are normalized as page percentages. The browser preview supports pointer dragging and DOCX writes the same logo as a floating page-positioned image, preserving transparency.

### D11: Template Creator is a single-viewport tool

Template Creator intentionally disables page/footer scrolling. Blocks are reordered with native drag-and-drop and their eye icons directly toggle visibility. Properties are split into Template/Header/Block/Logo tabs so all editing controls remain reachable within one viewport. Back/refresh warns before discarding dirty template changes.
