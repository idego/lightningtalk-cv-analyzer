## 1. Backend contract and extraction
- [x] 1.1 Add `CandidateProfile v1`, anonymization policy, strict extraction schema/prompt, and source-redacted extraction service.
- [x] 1.2 Add `POST /profile-builder/extract` with supported-file and AI-unavailable errors.

## 2. Snapshot rendering
- [x] 2.1 Add deterministic anonymization projection without mutating the canonical profile.
- [x] 2.2 Add IDEGO-style editable DOCX renderer and `POST /profile-builder/export/docx` using the submitted snapshot.

## 3. Frontend workflow
- [x] 3.1 Add authenticated proxy routes, sidebar destination, and `/profile-builder` page.
- [x] 3.2 Add upload/extraction state, canonical editor, anonymization controls, live preview, and DOCX download.

## 4. Verification
- [x] 4.1 Add domain/API regression tests covering schema, national-ID redaction, anonymization, and stale-state export.
- [x] 4.2 Run backend tests plus frontend typecheck/lint/unit tests and a production build under supported Node 22.
- [x] 4.3 Review the completed diff against repository standards and this change spec.
