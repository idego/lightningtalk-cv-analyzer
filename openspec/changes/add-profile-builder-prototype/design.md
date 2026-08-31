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
- Image/OCR ingestion, public API/Zapier, ATS/job-fit scoring, talent ranking, and arbitrary floating text-box layout that would turn editable DOCX into a poster-like document.

## Decisions

### D1: Profile Builder owns a separate domain contract

The existing AI analysis response is review-oriented and does not contain enough reconstruction detail. Profile Builder keeps its Pydantic profile/anonymization/rendering models together in one substantial `cv_validator/profile_builder.py` module. The existing `ai/request.py`, `ai/application.py`, `ai/openai_client.py`, and `ai/domain.py` are extended for the new structured extraction path rather than creating a parallel AI package. Model output omits UI IDs; code materializes stable per-section IDs after schema validation.

### D2: Extract only from the redacted canonical document

The endpoint reuses `ingest_cv()` and `redact_national_ids()` before creating a dedicated structured-output request. The prompt requires source-faithful extraction, null/empty values for missing facts, and no anonymization during extraction. The existing user-controlled AI setting is forwarded through the web proxy and enforced by the backend so disabling AI also disables Profile Builder model calls.

### D3: Keep one canonical client profile

One cohesive React workspace stores one `profile` object and one `anonymization` policy; field helpers stay local to that workspace instead of being split into many tiny components. The editor mutates only that canonical object. Preview applies anonymization as a pure derived projection. Export POSTs the exact current profile plus policy; it never relies on autosave or a profile ID.

### D4: Use `python-docx` for the first renderer

`python-docx` is already a project dependency and produces semantically editable Word documents. The prototype uses one constrained IDEGO-style flow template rather than introducing a new template engine before the workflow itself is validated.

### D5: Stage persistence and PDF after the first slice

The initial slice intentionally proved browser-state editing and DOCX correctness first. The later parity iteration adds snapshot persistence and PDF only after those invariants are covered by regression tests; PDF is derived from the exact DOCX through LibreOffice rather than introducing a second renderer.


### D6: Persist exact Profile Builder snapshots for Recent

Recent profiles use the existing SQLite persistence layer. A stored record contains the owner-scoped canonical `CandidateProfile`, anonymization policy, exact selected template snapshot, source filename, and created/updated timestamps. The original uploaded PDF/DOCX bytes are never stored. The editor autosaves the current snapshot after a debounce and opening Recent restores that exact state.

### D7: Use a constrained normalized template model

The Template Creator edits a `profile-template-v1` JSON contract rather than raw DOCX/Jinja/pdfme data. V1 supports brand text/accent, font family/sizes, header visibility, ordered domain sections, section titles, visibility, and simple inline/bulleted list presentation. It deliberately excludes arbitrary coordinates, overlap, rotation, and free-form drawing.

The same exact template snapshot is sent with DOCX export, avoiding a save/export race. The browser preview and DOCX renderer both consume the same normalized template contract.

### D8: Keep template management inside the Profile Builder flow

The upload state shows the current template beside Recent profiles. A template manager dialog can select a template, create a new one, or navigate to editing an existing one. `/profile-builder/templates/new` and `/profile-builder/templates/<id>` render the same Template Creator screen. Custom templates are explicitly Private or Shared and default to Private. The built-in `idego-default` is Shared and any customization remains an internal-team template rather than becoming a silent per-user fork.


### D9: Keep AI Summary cheap and source-faithful

AI Summary uses the existing pinned `gpt-5.6-luna` model with `reasoning.effort = none`, no tools, response storage disabled, and a 384-token output ceiling. The request excludes personal/contact data and the existing Summary so regeneration is grounded in professional profile facts rather than its own previous output. Recruiter instructions or pasted job descriptions may steer focus, tone, or language but are explicitly not a source of candidate facts. The returned text replaces the one canonical `profile.summary` value and therefore flows through autosave, preview, and export automatically.

### D10: Allow one constrained free-position logo element

The document flow remains constrained to semantic profile blocks. The only V1 free-positioned canvas element is an optional company logo. HR may upload PNG, JPG, WebP, or SVG; the browser sanitizes SVG network/script content and normalizes every upload to bounded PNG data stored in the template snapshot. Position and width are normalized as page percentages. The browser preview supports pointer dragging and DOCX writes the same logo as a floating page-positioned image, preserving transparency.

### D11: Template Creator is a single-viewport tool

Template Creator intentionally disables page/footer scrolling. Blocks are reordered with native drag-and-drop and their eye icons directly toggle visibility. Properties are split into Template/Header/Block/Logo tabs so all editing controls remain reachable within one viewport. Back/refresh warns before discarding dirty template changes.


### D12: Direct-manipulation A4 canvas uses editable-document lanes

Template sections are draggable both in the Blocks list and directly on the rendered A4 page. Horizontal pointer position snaps a body section to `left`, `full`, or `right`, while vertical drop position updates section order. Browser preview renders those same lanes. DOCX renders `full` sections as ordinary flowing content and consecutive side-lane sections inside a normal two-column table, preserving meaningful Word editing. Only the logo uses absolute page coordinates.

### D13: Separate organization schema from per-user conversion defaults

Custom-field definitions are organization-wide internal configuration because fields such as availability/rate should mean the same thing across recruiters. Their current definitions/defaults are copied into newly extracted canonical profile snapshots; changing or deleting a definition never rewrites historical snapshots. Conversion preferences are owner-scoped: default anonymization, auto-summary/prompt, technology aggregation, date formatting, default template, and filename convention. Upload is disabled until these defaults are loaded to avoid a first-click race.

### D14: Keep AI rewrites reviewable and away from internal metadata

AI Actions and Translation share one `ProfessionalProfile` transformation path using pinned `gpt-5.6-luna`, `reasoning.effort = none`, no tools, and response storage disabled. Personal/contact fields and organization custom fields are not sent. The backend rejects changes to unselected sections, preserves stable repeated-entry IDs, and applies additional protected-fact checks during translation. The browser presents Before/Proposed values per section; canonical state changes only after selective Accept.

### D15: Explicit template sharing

New custom templates are Private by default. A recruiter may explicitly change Access to Shared, making the same normalized template visible/editable to the authenticated internal team. The built-in IDEGO template is always Shared. Profile snapshots remain owner-scoped; sharing template design does not implicitly share candidate PII.

### D16: Derive PDF from DOCX and keep batch orchestration in the web workflow

PDF export renders the exact current DOCX bytes and converts them through isolated headless LibreOffice with a temporary HOME/UserInstallation and timeout. The API runtime image includes LibreOffice Writer. Batch Convert accepts at most 10 PDF/DOCX files and deliberately processes them through the same single-file extraction and snapshot-persistence path with explicit queued/processing/completed/failed UI state. Source file bytes remain browser/request-local and are never persisted by Profile Builder.
