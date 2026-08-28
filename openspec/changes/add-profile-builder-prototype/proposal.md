## Why

IDEGO currently relies on an external CV-to-profile workflow whose editor, preview, and export can drift apart. The existing CV Analyzer already owns secure PDF/DOCX ingestion, national-ID redaction, OpenAI configuration, authentication, and the web shell, so a separate product would duplicate the hardest infrastructure.

## What Changes

- Add a top-level **Profile Builder** workflow beside Analyze and Settings.
- Extract an uploaded PDF/DOCX into a dedicated versioned `CandidateProfile` contract without reusing the analysis-report schema.
- Keep one canonical browser-side profile state; editor, preview, anonymization, and export derive from the same current snapshot.
- Add deterministic, reversible anonymization controls for candidate PII and employer/institution visibility.
- Export one IDEGO-style, meaningfully editable DOCX directly from the submitted current profile snapshot.
- Keep the prototype session-only: no candidate-profile persistence, PDF conversion, or visual template studio in this slice.

## Capabilities

### New Capabilities

- `profile-builder`: Internal CV-to-editable-profile workflow with structured extraction, editing, anonymization, preview, and DOCX export.

## Impact

- One consolidated backend `cv_validator.profile_builder` profile/rendering module, extensions to the existing `ai/*` modules for extraction, and two API endpoints.
- New authenticated Next.js route and proxy handlers.
- Sidebar gains Profile Builder.
- No location score, band, Analyze behavior, persistence schema, or research behavior changes.
- No new runtime dependency is required for DOCX generation because `python-docx` is already installed.
