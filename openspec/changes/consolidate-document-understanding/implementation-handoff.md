# Implementation handoff

## Acceptance evidence

- OpenSpec tasks: 40/40 checked after implementation and verification.
- Backend: 563 tests passed in the rebuilt Docker test image; one upstream
  Starlette/httpx deprecation warning remains.
- Frontend: four Node test files passed, TypeScript passed, and the Next.js
  production build passed both locally and in the rebuilt development stack.
- OpenSpec: strict validation passed and all four planning artifacts are complete.
- Real UI: the previously verified synthetic-only UI flow rendered code-owned education,
  employment, and ESCO skills; AI disablement removed research controls; a
  synthetic legacy-null report reopened through the legacy selector; hidden
  organization, role, and date spans stayed quarantined while visible skill
  evidence survived.
- Final stack smoke: a freshly rebuilt isolated stack reported database and
  GeoNames ready with AI intentionally disabled, and its runtime image produced
  code-owned employment, explicit ESCO skills, and bounded research subjects
  from an anonymous synthetic document. Temporary containers and volumes were
  removed afterwards.
- Evaluation: the committed anonymous supported-pattern suite passed every
  specified precision, recall, exact-match F1, unsupported-positive-field, and
  same-input reproducibility threshold.
- Persistence and compatibility: focused tests cover initial save, reload, AI
  retry replacement, retention, deletion, malformed payloads, legacy-null loads,
  explicit timeline relationships, and frozen independent Structural Audit V1
  golden output.

The frontend linter still reports the pre-existing
`src/hooks/use-mobile.ts` synchronous-effect state update, plus three unrelated
warnings. No assertion or lint rule was weakened for this change.

## Commit policy and product acceptance

The user explicitly authorized local logical Conventional Commits and prohibited
pushing. Commit boundaries are repository-history checkpoints only; the task
checkboxes above represent product acceptance evidence and are not inferred from
the existence of a commit. No push was performed.

## Scope and privacy

The implementation preserves deterministic scoring authority and existing
weights, keeps Structural Audit V1 as a one-release compatibility projection,
uses only an offline index compiled from the pinned official ESCO 1.2.0 RDF
export at runtime, and adds no OCR, service, or
runtime network parser. Verification fixtures and UI uploads are synthetic and
anonymous. The two unrelated contextual OpenSpec directories were not changed.
