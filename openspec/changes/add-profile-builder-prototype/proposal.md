## Why

IDEGO currently relies on an external CV-to-profile workflow whose editor, preview, and export can drift apart. The existing CV Analyzer already owns secure PDF/DOCX ingestion, national-ID redaction, OpenAI configuration, authentication, and the web shell, so a separate product would duplicate the hardest infrastructure.

## What Changes

- Add a top-level **Profile Builder** workflow beside Analyze and Settings.
- Extract an uploaded PDF/DOCX into a dedicated versioned `CandidateProfile` contract without reusing the analysis-report schema.
- Keep one canonical browser-side profile state; editor, preview, anonymization, and export derive from the same current snapshot.
- Add deterministic, reversible anonymization controls for candidate PII and employer/institution visibility.
- Export one IDEGO-style, meaningfully editable DOCX directly from the submitted current profile snapshot.
- Persist extracted/edited profile snapshots for a Recent profiles workflow without storing the original CV bytes.
- Add persistent constrained templates, a template picker/manager, and a visual Template Creator screen.
- Add a promptable GPT-5.6 Luna AI Summary action that writes into the canonical Summary field.
- Make Template Creator a fixed no-scroll workspace with drag-reordered blocks, direct eye visibility toggles, unsaved-change protection, and one freely positioned uploaded logo.
- Add PDF export from the exact DOCX snapshot, organization custom fields, reviewable AI Actions/Translation, per-user conversion defaults, controlled template sharing, batch conversion, and a searchable Profiles catalog.
- Let Template Creator blocks be dragged directly on the A4 canvas; body blocks snap to editable-DOCX `left/full/right` lanes while the logo remains freely positioned.

## Capabilities

### New Capabilities

- `profile-builder`: Internal CV-to-editable-profile workflow with structured extraction, editing, anonymization, preview, and DOCX export.

## Impact

- Extend the consolidated backend `cv_validator.profile_builder` profile/rendering module with the normalized template contract and template-aware DOCX rendering.
- Extend the existing SQLite `PersistenceStore` with owner-scoped candidate-profile snapshots/preferences, organization custom-field definitions, and private/shared templates; original CV bytes are not persisted.
- Extend the existing Profile Builder API/proxy surface with profile/template/custom-field/preferences CRUD, PDF export, and reviewable AI transforms.
- Extend the authenticated workflow with Recent profiles, a searchable Profiles catalog, batch conversion, template selection/management, autosave, AI review flows, and a dedicated Template Creator screen.
- Sidebar gains Profile Builder and Profiles.
- No location score, band, Analyze behavior, persistence schema, or research behavior changes.
- DOCX continues to use `python-docx`; PDF adds LibreOffice Writer to the API runtime image and converts the exact rendered DOCX in an isolated headless process.
