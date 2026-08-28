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
- Keep PDF conversion and unconstrained canvas editing outside this slice.

## Capabilities

### New Capabilities

- `profile-builder`: Internal CV-to-editable-profile workflow with structured extraction, editing, anonymization, preview, and DOCX export.

## Impact

- Extend the consolidated backend `cv_validator.profile_builder` profile/rendering module with the normalized template contract and template-aware DOCX rendering.
- Extend the existing SQLite `PersistenceStore` with owner-scoped candidate-profile snapshots and templates; original CV bytes are not persisted.
- Extend the existing Profile Builder API/proxy surface with recent-profile and template CRUD.
- Extend the authenticated Profile Builder route with Recent profiles, template selection/management, autosave, and a dedicated Template Creator screen.
- Sidebar gains Profile Builder.
- No location score, band, Analyze behavior, persistence schema, or research behavior changes.
- No new runtime dependency is required for DOCX generation because `python-docx` is already installed.
