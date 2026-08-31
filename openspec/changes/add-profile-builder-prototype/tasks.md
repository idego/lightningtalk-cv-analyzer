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


## 9. CVtoBlind parity workflow
- [x] 9.1 Add authoritative PDF export by converting the exact rendered DOCX snapshot through isolated headless LibreOffice.
- [x] 9.2 Add organization custom-field definitions, snapshot values, editor controls, and a template-renderable Custom Fields block.
- [x] 9.3 Add GPT-5.6 Luna AI Actions with selected-section rewriting, preview/diff review, and selective Accept into canonical state.
- [x] 9.4 Add owner-scoped conversion settings for auto-summary/default prompt, default anonymization, technology aggregation, date formatting, default template, and output filename convention.
- [x] 9.5 Allow templates to be explicitly Private or Shared; shared templates are visible/editable to the internal team while private templates remain owner-scoped.
- [x] 9.6 Add a dedicated batch conversion flow for up to 10 PDF/DOCX files with queued/processing/completed/failed states and no image/OCR input.
- [x] 9.7 Add GPT-5.6 Luna translation passes with language selection, preview/diff review, and selective Accept.
- [x] 9.8 Add an authenticated Profiles catalog/search screen while keeping Recent profiles on the upload page as a shortcut.
- [x] 9.9 Verify all new workflows with focused tests, full regression, Node 22 production build, browser smoke, and whole-diff review.


## 10. AI transform latency
- [x] 10.1 Prune AI Action context by selected section and make Translation selected-section-only.
- [x] 10.2 Use low verbosity, stable prompt caching, and dynamic output-token caps for profile transforms.
- [x] 10.3 Run focused payload-contract tests, full regression, production build, and diff review.

## 11. Whole-branch hardening and seam cleanup
- [x] 11.1 Re-sanitize structured profile/config/AI/output boundaries and add explicit untrusted-candidate prompt-injection rules.
- [x] 11.2 Require owner auth for every Profile Builder backend action and add a backend-enforced 10 MiB per-file upload limit.
- [x] 11.3 Fix debounce data-loss on navigation and reconcile autosave state from the server-normalized snapshot.
- [x] 11.4 Make persisted preferences authoritative for the default template and handle stale defaults/private shared-template overrides correctly.
- [x] 11.5 Enforce custom-field kind/value semantics and national-ID-safe identifiers.
- [x] 11.6 Consolidate OpenAI Responses transport handling for structured transforms and Summary.
- [x] 11.7 Extract shared browser domain contracts/defaults, A4 preview, and typed Profile Builder API client into deep modules without fragmenting the editor into micro-components.
- [x] 11.8 Run final focused/full regression, production build, browser smoke, and whole-branch review after the hardening refactor.
