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


## 5. Recent profiles and autosave
- [x] 5.1 Extend SQLite persistence/API with owner-scoped candidate profile snapshots without storing source CV bytes.
- [x] 5.2 Create saved profiles after extraction, add debounced snapshot autosave, and render Recent profiles below upload with open/delete actions.

## 6. Templates and creator
- [x] 6.1 Add `profile-template-v1`, built-in IDEGO Default, owner-scoped template persistence/API, and template-aware DOCX rendering.
- [x] 6.2 Add current-template card and manager dialog with select/create/edit actions.
- [x] 6.3 Add one constrained Template Creator screen with domain blocks, ordering, visibility, headings, branding, typography, and sample preview.
- [x] 6.4 Send the exact current template snapshot through preview, autosave, reopen, and DOCX export.

## 7. Follow-up verification
- [x] 7.1 Add persistence/template/API/export regression tests, including owner isolation and custom-template semantics.
- [x] 7.2 Run backend full suite, frontend typecheck/lint/unit tests, and Node 22 production build.
- [x] 7.3 Review the whole diff from `origin/feature/cv-analyzer-development` for standards/spec drift and push the updated branch.


## 8. Creator direct manipulation and AI summary
- [x] 8.1 Replace block move arrows with drag-and-drop and move visibility to the block eye icon.
- [x] 8.2 Make Template Creator a fixed no-scroll viewport and protect dirty Back/browser-unload navigation.
- [x] 8.3 Add sanitized PNG/JPG/WebP/SVG logo upload, direct page dragging/resizing, persistence, preview, and floating DOCX rendering.
- [x] 8.4 Add promptable/regeneratable GPT-5.6 Luna Summary generation with reasoning disabled and a small token budget.
- [x] 8.5 Run full regression, production build, browser smoke, and whole-diff review after these changes.
