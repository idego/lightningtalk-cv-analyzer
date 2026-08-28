## 1. Structural audit contract and configuration

- [x] 1.1 Define the exact `structural_audits` domain/API schema, enums, nullable fields, source-location association states, safe evidence shapes, stable ordering, and per-file limits; verify JSON-safe round-trip tests cover every status and legacy `null` behavior.
- [x] 1.2 Add versioned structural-audit configuration with the documented size, opacity, luminance, meaningful-content, atom/run, excerpt, and observation defaults; verify valid defaults and invalid values with focused tests.
- [x] 1.3 Add stable structural reason/trigger codes and English/Polish copy without adding structural IDs to the fixed checklist records; verify locale rendering changes prose only and preserves machine-readable codes.

## 2. Canonical provenance and format coverage

- [x] 2.1 Build canonical text and format presentation spans from shared PDF character/DOCX text-node provenance, including `exact`, `partial`, and `unmapped` associations; verify existing canonical text and deterministic location outputs stay invariant on compatibility fixtures.
- [x] 2.2 Carry presentation associations and national-ID redaction-span metadata through the raw-to-redacted document flow; verify an ID-only hidden span remains locatable by safe metadata after same-length masking.
- [x] 2.3 Add bounded PDF page-text-span inspection for size, color, opacity, paint/background evidence, and coordinates; verify synthetic PDFs cover exact/partial/unmapped mapping, missing attributes, and pre-materialization atom limits.
- [x] 2.4 Add bounded DOCX body-paragraph and table-cell run inspection for hidden flags, inherited/explicit size/color/shading, and logical pages; verify headers, footers, textboxes, footnotes/endnotes, comments, drawings, and embedded files are surfaced as omitted coverage rather than silently included.
- [x] 2.5 Isolate malformed or unsupported presentation parts from base ingestion; verify the report returns honest `partial`/`unavailable` coverage and still completes canonical text analysis.

## 3. Deterministic timeline audit

- [x] 3.1 Implement the two-stage date-like lexer/validator for numeric, English, and Polish month/year forms, bounded separators, open-ended tokens, invalid months, and start-after-end periods; verify malformed tokens such as `00/2024` and `13/2024` become invalid observations instead of disappearing.
- [x] 3.2 Implement line-bounded entry association, reviewed employment/education/other heading state, ambiguous `unknown` handling, and exclusion labels for birth/contact/certification/project/publication dates; verify negative fixtures cannot create employment or education overlaps.
- [x] 3.3 Inject one analysis snapshot month into timeline normalization and persist it in the structural result; verify `present/current/now` produces the same month across repeated runs and AI retry/reload paths.
- [x] 3.4 Implement precision-aware month intervals, invalid-entry exclusion, and merged non-overlapping duration summaries; verify month/year/mixed precision, valid future ranges, and exact duration boundaries.
- [x] 3.5 Implement same-category overlap detection with adjacency handling, exact shared-month counts, possible-overlap precision notes, stable pair ordering, and duplicate suppression; verify employment/education isolation and concurrent-work neutral language.

## 4. Hidden and low-visibility audit

- [x] 4.1 Implement explicit hidden/vanished, near-zero size, near-zero opacity, and known-light-background contrast rules with normalized units, DOCX style inheritance, and PDF paint-order checks; verify the `0.5px`-equivalent fixture is caught while ordinary and light-on-dark text is not.
- [x] 4.2 Implement meaningful-content filtering, redaction exceptions, adjacent-span grouping, per-file limits, and pre-materialization resource caps; verify unknown backgrounds/attributes produce no positive finding and capped files return deterministic truncation/partial metadata.
- [x] 4.3 Enforce safe visibility output with no raw hidden excerpt, only bounded location/trigger/count/version/redaction metadata; verify a hidden national-ID fixture emits presence/type metadata without raw or partial identifier content in API, logs, or structural persistence.

## 5. Pipeline, report, persistence, and AI boundaries

- [x] 5.1 Run timeline and visibility audits after national-ID redaction using the injected snapshot and attach them to the report independently of AI; verify AI-disabled PDF, DOCX, and text-input runs return the expected timeline/visibility statuses.
- [x] 5.2 Keep structural data outside location scoring and automated actions; verify adding any structural observation leaves score, band, scoring signal count, and existing location findings byte-equivalent.
- [x] 5.3 Serialize the exact versioned structural object in API responses and preserve it through report reads and AI-retry replacement; verify old payloads remain readable and retry keeps the original snapshot/audit unchanged.
- [x] 5.4 Implement one structural sanitizer/allowlist for initial persistence and AI retry, rejecting unknown visibility fields and enforcing all counts/geometry/evidence limits; verify SQLite audit JSON and reopened payloads contain only safe structural data.
- [x] 5.5 Keep the structural object out of the AI input builder and public research requests while leaving the existing redacted CV-input contract explicit; verify the AI prompt/version is unchanged and AI `timeline_overlap` remains a distinct authority/code path.

## 6. Recruiter-facing report UI

- [x] 6.1 Add typed frontend models and a dedicated structural-audit panel/row renderer with explicit legacy, partial, unavailable, and not-applicable fallbacks; verify it does not pass visibility items through `ReviewFlag`, `FlagList`, or fixed checklist label lookup.
- [x] 6.2 Render timeline entries, invalid periods, exact/possible overlaps, duration/precision details, visibility triggers, safe source locations, counts, and coverage status; verify hidden text is never rendered and no structural item uses `SUSPICIOUS` or fraud language.
- [x] 6.3 Add complete English and Polish structural labels, explanations, and safe evidence controls; verify language switching changes only localized copy and preserves observation codes/source locations.
- [x] 6.4 Verify the structural panel coexists with existing findings, AI-disabled status, file details, research sections, and the decision-support disclaimer without adding score/band UI or replacing the base report.

## 7. End-to-end verification and handoff

- [x] 7.1 Add offline full-pipeline fixtures for valid/no-finding, invalid period, exact overlap, year-only possible overlap, hidden DOCX, tiny/white PDF, unsupported parts, truncation, and redacted-ID cases; verify API, persistence, coverage, and privacy assertions for each.
- [x] 7.2 Run backend/frontend regression suites and OpenSpec validation; verify structural tests, existing tests, and `openspec validate "add-cv-structural-audits" --strict` all pass.
- [x] 7.3 Prepare a concise manual QA checklist for the user covering one PDF and one DOCX, AI-disabled behavior, neutral labels, partial coverage, source verification, and score/band invariance; verify the handoff requires no automated browser upload or click.
