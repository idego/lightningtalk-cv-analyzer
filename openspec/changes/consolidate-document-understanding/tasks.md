## 1. Baseline and Additive Contract

- [x] 1.1 Record the focused backend and frontend baseline, isolate the known unrelated prompt-substring failure, and verify new failures can be attributed to this change without weakening assertions.
- [x] 1.2 Add the internal `document_understanding` package, bounded domain types, stable source-derived IDs, coverage states, and one service entry point over `RedactedDocument`; verify domain invariant, cross-reference, and deterministic ordering tests pass without extending `FactKind` or `ScoringSignalKind`.
- [x] 1.3 Implement the exact nullable `document-understanding-v1` DTO and numeric bounds from the spec with one serializer/sanitizer; verify valid, every-collection truncation, malformed enum/reference/evidence, unknown-field, internal-document/index/presentation-field rejection, forbidden-national-ID, and legacy-null tests pass.
- [x] 1.4 Add additive SQLite/API persistence and reload support that preserves understanding bytes across AI replacement, retention, and deletion; verify initial save, reload, retry replacement, legacy load, retention, and deletion tests pass.

## 2. Canonical Source Index and Visibility Quarantine

- [x] 2.1 Extend the existing PDF/DOCX ingestion result with reusable ordered block/source associations without changing canonical text, page IDs, line IDs, explicit DOCX pagination, or fail-soft coverage; verify paragraph, table, PDF geometry, page-break, and optional-metadata failure fixtures pass.
- [x] 2.2 Refactor downstream block/presentation/link consumers to use the reusable canonical surfaces instead of reopening or independently traversing submitted bytes; verify instrumentation tests demonstrate one configured adapter parse per analysis.
- [x] 2.3 Build one versioned exact-mapped visibility-exclusion index from existing structural thresholds after mandatory redaction; verify explicit-hidden, near-zero, zero-opacity, known-low-contrast, partial, unmapped, and redacted-span fixtures pass.
- [x] 2.4 Route current deterministic candidate materialization and new understanding annotations through the exclusion index; verify hidden-only, partial-overlap, hidden-label/visible-value, duplicate-hidden/visible, and multi-span phone, location, postal, organization, institution, date, and skill cases obey candidate-level provenance rules and cannot regain excluded evidence through grouping/deduplication.
- [x] 2.5 Prove ordinary visible fixtures retain byte-equivalent authorized facts, scoring signals, findings, numeric scores, and bands, and separately snapshot the intended hidden-only safety correction.

## 3. Shared Section, Date, and Entry Annotations

- [x] 3.1 Centralize versioned Unicode, whitespace, punctuation, alias, and token-boundary normalization used by section, record, skill, research, and reconciliation logic; verify Polish/English normalization and collision fixtures pass.
- [x] 3.2 Implement the bounded standard section catalog with exact aliases, supporting-only style/fuzzy evidence, source ranges, confidence, coverage, and stable IDs; verify all catalog categories, unknown headings, style-only false positives, mixed languages, and deterministic ordering fixtures pass.
- [x] 3.3 Consolidate current date candidates and structural range parsing into shared date-span/date-range annotations with snapshot, precision, invalid, unresolved, and stable-ID behavior; verify the existing timeline grammar and malformed/open-ended/coarse fixtures pass unchanged.
- [x] 3.4 Adapt Structural Audit to project timeline entries and observations from shared section/date annotations while preserving the `structural-audits-v1` serialized contract for equivalent fixtures.
- [x] 3.5 Implement one conservative entry-boundary builder over canonical paragraphs, list items, table rows, date anchors, spacing, and source order; verify duplicate periods, wrapped entries, tables, mixed Polish/English content, and ambiguous/interleaved layout abstention fixtures pass.
- [x] 3.6 Add explicit record-to-section and record-to-date relationships and update new-report projections to avoid date-string joins; verify two records with identical displayed dates remain distinct and correctly associated.

## 4. Code-Owned Education and Employment Records

- [x] 4.1 Materialize education records from accepted sections/entry spans with independently evidenced institution, program, degree, dates, result, and location fields; verify required-identity, optional-unknown, confidence, evidence, and abstention fixtures pass.
- [x] 4.2 Materialize employment records from the same entry mechanism with independently evidenced organization, role, relationship, dates, and location fields; verify required-identity, optional-unknown, employer/client ambiguity, and confidence fixtures pass.
- [x] 4.3 Represent self-employed/freelance values as relationships unless a distinct business, employer, or client is source-supported; verify generic relationship labels never become organization records or subjects.
- [x] 4.4 Add deterministic deduplication that preserves distinct source records, stable IDs, field authority, and all bounded evidence; verify repeated text and identical-date fixtures do not collapse unrelated entries.
- [x] 4.5 Add immutable code-first company/education research subjects from supported record identity fields and verify normalization keys, stable source order, subject bounds, self-employment exclusions, and no PII/excerpts in subjects.
- [x] 4.6 Pass the first-boundary gate covering exact schema/sanitizer, source reuse, quarantine, shared annotations, structural byte compatibility, conservative education/employment, immutable code subjects, visible deterministic byte invariance, persistence/retry/legacy reads, and privacy before starting skills, AI reconciliation, or frontend default switching.

## 5. Versioned Explicit-Skills Extraction

- [ ] 5.1 Add an offline skill-index build and validation command for one pinned reviewed ESCO input, including source/license URL, version, filtering rules, input/output checksums, language/alias counts, and a compiled manifest; verify reproducible output and checksum-failure tests pass without runtime network or a new service.
- [ ] 5.2 Implement the replaceable exact normalized phrase/token-boundary matcher using the existing Python runtime only; verify canonical IDs, aliases, duplicate evidence, mixed languages, and deterministic output without spaCy, O*NET, pretrained models, or downloads.
- [ ] 5.3 Restrict skill materialization to accepted skills sections or clearly labelled lists and verify explicit-list fixtures pass.
- [ ] 5.4 Add fail-closed handling for ambiguous short labels, fuzzy-only suggestions, missing/invalid taxonomy data, and unsupported context; verify `Go`, `R`, `C`, ordinary-word collisions, prose false positives, and unavailable-coverage fixtures pass.

## 6. Research Projection and AI Enrichment

- [ ] 6.1 Derive each authorized research-request union from immutable code subjects first and independently supported AI additions second, using the specified exact dedupe key and existing category cap; verify AI additions cannot displace, mutate, or reorder code subjects and safe requests contain only allowlisted public subjects.
- [ ] 6.2 Refactor company and education research request builders to consume that derived union while keeping LinkedIn behavior unchanged; verify overall-AI-disabled, public-research-disabled, document-AI-failed-but-research-enabled, code-only, AI-only, duplicate, retry, limit, and cache-isolation states separately.
- [ ] 6.3 Build a same-length masked visible-source AI projection with stable page/line IDs and offsets, extend the request with bounded code-owned context, and reject every AI field/finding whose evidence intersects quarantine; verify hidden characters never reach provider inputs, accepted outputs, research requests, cache keys, persistence, logs, or exceptions.
- [ ] 6.4 Implement authority-preserving reconciliation that lets AI fill independently supported optional fields or add supported records but never delete, downgrade, or overwrite code-owned fields; verify omission, compatible enrichment, conflict, invalid evidence, timeout, refusal, and partial-validation fixtures pass.

## 7. Frontend Dual-Read Migration

- [ ] 7.1 Add frontend types and selectors for nullable V1 understanding data, preferring code-owned records and validated AI-only additions for new reports while retaining AI fallback for legacy reports; verify selector tests cover new, mixed, legacy, and unavailable payloads.
- [ ] 7.2 Render education, employment, and explicit skills with visible code/AI authority, confidence, field-level unknowns, and existing report layout conventions; verify component tests cover collapse, ordering, duplicate suppression, and partial coverage.
- [ ] 7.3 Replace new-report structural entity association by displayed date strings with explicit stable relationships while retaining the legacy fallback; verify identical-date records attach the correct organization/institution.
- [ ] 7.4 Keep company/education research controls available from code-owned subjects only when public research remains authorized after document-AI failure, and keep all three controls disabled when the overall AI/public-research switch is off; verify UI tests distinguish every authorization/outcome combination.

## 8. Evaluation, Optional Library Spike, and Delivery Gates

- [ ] 8.1 Add synthetic/anonymous fixtures for headings/no headings, duplicate periods, DOCX tables, mixed Polish/English sections, self-employment, employer/client ambiguity, open-ended dates, hidden/low-visibility spans, ambiguous short skills, and interleaved PDF columns; verify no committed fixture or output contains candidate PII.
- [ ] 8.2 Add understanding evaluation metrics for section boundaries, record identity, per-field support, skill precision, abstention, coverage, research subjects, and same-input reproducibility; on committed supported-pattern fixtures require section precision >= 0.98 and recall >= 0.95, institution/employer identity precision >= 0.98, structured-entry exact-match F1 >= 0.90, explicit-skill precision >= 0.99, zero unsupported positive fields, and identical repeated output; report private-corpus metrics separately without committing inputs or extracted text.
- [ ] 8.3 Verify national IDs in body text, tables, dates, skills, hidden spans, AI requests, API payloads, SQLite, exceptions, and logs never expose raw, hashed, or partially revealed values.
- [ ] 8.4 Run strict OpenSpec validation, the complete backend suite, frontend tests/type checks/production build, persistence compatibility checks, and relevant linters; record any pre-existing unrelated failure rather than weakening the gate.
- [ ] 8.5 Rebuild the local development stack and verify through the real UI that code-owned education/employment/skills survive document-AI omission/failure, overall-AI disablement still disables research, enabled research eligibility remains bounded/code-first, hidden-only content is quarantined, legacy reports reopen, and score/band behavior matches the specified invariants.
- [ ] 8.6 Remove only the duplicate date/section traversal paths whose consumers have migrated, retain compatibility wrappers for one release, update architecture/operations documentation, and verify no production consumer imports the retired paths.
- [ ] 8.7 Verify the branch has no unintended files, secrets, PII, or unrelated OpenSpec changes and that the implementation handoff records the user-authorized Conventional Commit policy separately from product acceptance tasks.
