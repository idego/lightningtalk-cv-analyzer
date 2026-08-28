## Context

See `proposal.md` for motivation. The repository already has the required architectural foundations: PDF/DOCX adapters produce `RawDocument`; mandatory national-ID masking produces `RedactedDocument`; deterministic extraction returns `Candidate`, `Fact`, `Observation`, and `ScoringSignal`; scoring is a separate pure projection; Structural Audit and AI validation have their own bounded public contracts.

The fragmentation occurs after redaction. `pipeline._analyze_raw()` independently runs structural audit and deterministic extraction over the same canonical pages. Candidate extraction and Structural Audit recognize dates separately. Structural Audit recognizes section state but does not expose it to research. Company and education research require AI-authored facts/candidates, and the frontend associates some structural entries with AI records through displayed date strings.

A safety review also established that exact-mapped hidden or near-zero PDF text currently remains in canonical text and may become a deterministic candidate. Consolidation therefore needs a shared visibility-exclusion index before materialization; merely reusing the current outputs would preserve an unsafe input path.

The deployment remains the existing Python/FastAPI process and SQLite store in the current Compose stack. The design cannot add a document service, remote parser, OCR service, runtime PII-bearing enrichment, or AI verdict authority.

## Goals / Non-Goals

**Goals:**

- Add one additive document-understanding vertical slice over existing domain and ingestion types.
- Compute reusable visibility exclusions, sections, dates, entry spans, structured records, and research subjects once per analysis.
- Materialize conservative code-owned education, employment, and explicit skills data while detecting the complete bounded standard section catalog.
- Reuse shared annotations in Structural Audit and research without changing their external contracts.
- Keep existing visible-input scoring behavior invariant while excluding exact-mapped hidden-only values before all materialization.
- Preserve legacy reports and AI fields through an explicit dual-read migration.
- Make AI an enrichment/reconciliation consumer rather than the sole owner of structured CV facts.

**Non-Goals:**

- Rewriting `RedactedDocument`, `DeterministicAnalysisResult`, scoring, FastAPI, SQLite, or the frontend architecture.
- Replacing `pdfplumber` or `python-docx` during the production implementation.
- OCR, rendered DOCX pagination, generalized column reconstruction, image understanding, or inference over unsupported document surfaces.
- Fully materializing semantic records for certifications, projects, languages, publications, awards, volunteering, references, or summary in V1. Their section boundaries are detected and preserved for later schemas.
- Removing legacy AI education/employment facts in V1.
- Sending CV content to ESCO, O*NET, Docling services, or any external parser.
- Adding education, employment, skills, or research subjects to scoring.

## Decisions

### 1. Add an aggregate over existing types, not a replacement document model

Add an internal `cv_validator.document_understanding` package with one public service entry point and an additive aggregate conceptually shaped as:

```python
DocumentUnderstandingResult(
    document: RedactedDocument,
    annotation_index: DocumentAnnotationIndex,
    deterministic: DeterministicAnalysisResult,
    structural_audits: StructuralAuditResult,
    sections: tuple[SectionSpan, ...],
    records: tuple[StructuredRecord, ...],
    skills: tuple[SkillMatch, ...],
    code_research_subjects: tuple[ResearchSubject, ...],
    coverage: UnderstandingCoverage,
)
```

`RedactedDocument` remains the canonical text/provenance source. Existing deterministic and structural results remain their current public projections. Education/employment/skills records use a distinct typed authority surface and do not extend `FactKind` or `ScoringSignalKind`, whose narrow graph validation protects the verdict.

Alternative considered: replace ingestion/domain types with `DoclingDocument` or a new generic AST. Rejected because it creates a rewrite, changes authority boundaries, and makes rollback difficult.

### 2. Give the vertical slice one service boundary but retain focused internal stages

The package may contain focused files, but only the service orchestrator can run a document-understanding analysis. The stages are pure transformations over one shared source/index:

```text
RedactedDocument
  -> source/presentation index
  -> visibility quarantine
  -> lexical annotations
  -> section/date/entry annotations
  -> structured records and skills
  -> existing deterministic projection
  -> structural projection
  -> research-subject projection
```

No stage reopens submitted bytes. No downstream consumer runs global source regexes when the equivalent shared annotation exists. Compatibility wrappers such as `audit_document(document)` may remain during migration but delegate to the shared annotator/projector.

Alternative considered: one large implementation module. Rejected because one pass and one ownership boundary do not require mixing parsing, projection, sanitization, and adapters in one file.

### 3. Build visibility quarantine before positive materialization

The first shared index maps exact presentation spans to canonical page offsets. Supported high-confidence triggers include explicit hidden text, near-zero size, zero opacity, and deterministically established low contrast according to the existing versioned thresholds. A complete candidate/field span contained only in excluded intervals is unavailable to:

- current deterministic candidates and score facts;
- structured records and skills;
- research subjects;
- AI code-owned context.

The visibility observation remains a neutral bounded output. Partial/unmapped spans are not subtracted because doing so could remove visible content. Redaction remains earlier than disclosure and exclusion metadata contains no prohibited identifier value.

This intentionally changes results only where an existing candidate was sourced exclusively from exact-mapped hidden content. Golden visible fixtures must remain invariant; dedicated fixtures record the corrected hidden-content behavior.

Alternative considered: quarantine only new structured records. Rejected because it would preserve inconsistent authority in which the same hidden value is untrusted for research but trusted by scoring.

### 4. Use one annotation graph with stable source-derived IDs

Internal annotation types include:

- `SourceBlock` / source index views over existing pages and presentation spans;
- `SectionSpan` with catalog kind, heading evidence, range, confidence, and coverage;
- `DateSpan` and `DateRange` with literal, normalized endpoints, precision, validity, and snapshot;
- `EntrySpan` with owning `section_id` and included source range;
- `StructuredRecord` with category and independently evidenced `StructuredField` values;
- `SkillMatch` with taxonomy identifier and source evidence;
- `ResearchSubject` with category, normalized public subject, authority, and originating record.

IDs are deterministic within the redacted document and include category plus source identity/position. Structural Audit V1 remains byte-compatible and does not gain new fields; `document_understanding.timeline_record_links` explicitly maps its existing timeline entry IDs to structured record IDs. UI and backend joining by normalized displayed date is retired for new reports; legacy reports retain the fallback.

Alternative considered: content hashes as the only IDs. Rejected because identical dates or repeated headings need distinct identities and localized display changes must not break relationships.

### 5. Detect all standard sections but materialize only three V1 schemas

The section catalog is centralized and versioned. Exact normalized heading aliases can establish sections; style and bounded fuzzy similarity only strengthen lexical/contextual evidence. V1 materializes:

- education records;
- employment records, including relationship type;
- literal skills from explicit skills sections or clearly labelled lists.

Other catalog sections are useful code-owned boundaries but remain unparsed content in V1. This produces a complete structural map without pretending that every category already has a reliable semantic schema.

One entry builder groups source blocks using common paragraph/list/table-row/date/spacing signals. Category schemas select fields from the resulting span; they do not each implement heading, date, or global traversal logic.

Alternative considered: implement every record schema in one release. Rejected because confidence rules and evaluation sets differ, and an all-category semantic parser would turn this consolidation into a rewrite.

### 6. Consolidate existing date behavior without extending grammar in V1

The existing structural month/range parser becomes the authoritative date-range normalizer. Existing candidate disclosure consumes its annotations rather than maintaining a second grammar. Open-ended endpoints use the persisted analysis snapshot month. Invalid and coarse precision are preserved.

No new date dependency is added in V1. A later `dateparser` evaluation may normalize only spans already identified by bounded grammar; global `search_dates()` remains prohibited and adoption requires a separate reviewed change.

### 7. Use local ESCO taxonomy data and the existing Python runtime

Skill extraction consumes a versioned compiled local ESCO index because ESCO is multilingual and EU-maintained. The reviewed ESCO source archive is a build input, not a runtime network dependency. The compiled index has a manifest containing source version/URL, license attribution, input and output checksums, build version, language selection, alias counts, and filtering rules.

The V1 matching interface supports exact normalized phrase and token-boundary matches using the existing Python runtime and a compiled alias lookup. It does not add spaCy, a pretrained model, RapidFuzz, O*NET, or runtime downloads. Those remain possible later substitutions behind the same boundary after a separate dependency, license, and operational review.

Missing or invalid skill data marks only skills coverage unavailable; it does not prevent analysis startup in V1.

Alternative considered: ESCO Local API. Rejected because it adds an unnecessary service. Alternative considered: a hand-maintained complete skill list. Rejected because it recreates taxonomy work and lacks multilingual provenance.

### 8. Keep production adapters and defer parser-library replacement

`pdfplumber` and `python-docx` remain the production adapters. Their existing page IDs, canonical text, explicit DOCX page-break policy, fail-soft presentation behavior, metadata allowlist, and hyperlink extraction remain authoritative.

Docling, Unstructured, and PyMuPDF are not installed or benchmarked as delivery tasks for this change. A later Docling spike may compare reading order, tables, headings, source provenance, latency, peak memory, container size, model licenses, and cold start using pinned offline artifacts. PyMuPDF remains excluded absent an approved AGPL/commercial license decision.

### 9. Project research subjects from code plus validated AI additions

The code-owned record projector persists immutable bounded company and education subjects only from independently supported public entity fields. Existing safe-subject rules, self-employment exclusions, category limits, and reusable-cache privacy continue to apply.

AI validation produces independently evidenced additions with AI authority. Each authorized research request derives a union in code-first order: immutable code subjects consume the existing category limit first, followed by deduplicated AI additions. The union is not written back to document understanding. It never upgrades AI authority to code or deletes/reorders code subjects. Company and education request builders consume this derived projection only when the overall AI/public-research switch remains enabled. LinkedIn remains unchanged in V1 because it is candidate-scoped and must not be inferred from entity extraction.

### 10. Use additive persistence and dual-read UI migration

New reports add the exact top-level `document_understanding` contract specified in `specs/document-understanding/spec.md`. The public DTO deliberately excludes the canonical document, raw annotation index, presentation metadata, and excluded source text. One sanitizer is used on initial persistence, API serialization, reload, and AI replacement. Retry replaces only AI state and preserves immutable understanding bytes plus snapshot, stable IDs, and code subjects.

For new reports, frontend overview/research prefer code-owned records and then show independently validated AI-only additions. Legacy reports with no understanding payload retain current AI-derived display and research behavior. Legacy AI facts remain persisted in V1, allowing rollback without data migration.

Alternative considered: migrate or rewrite all stored reports. Rejected because the existing nullable-version pattern supports safer additive rollout.

### 11. Send AI a stable filtered source projection

The canonical redacted document remains unchanged for stable persistence identity and existing evidence mapping. The AI request builder creates a separate visible-source projection by replacing every exact quarantined interval with same-length masks. Page and line IDs plus offsets remain stable, but quarantined characters never reach the provider. AI response validation additionally rejects any field/finding whose required evidence intersects the exclusion index, preventing reconstructed hidden values from becoming facts or research subjects.

This resolves the tension between complete document review and hidden-content quarantine: AI receives the complete non-quarantined canonical surface, not the excluded characters. The filtered projection is not persisted as a second document.

Alternative considered: send canonical text and reject only returned hidden evidence. Rejected because it would still disclose quarantined CV content externally.

### 12. Make compatibility and privacy observable gates

Evaluation is layered:

- synthetic committed fixtures for deterministic CI;
- ignored private corpus for local precision/recall and layout evaluation;
- score/band/signals snapshots for visible inputs;
- section-boundary, record identity, field support, skill precision, abstention, and research-subject metrics;
- persistence/retry/legacy/API round trips;
- frontend type/test/build and local-stack report verification.

The known pre-existing brittle prompt substring test must be recorded or repaired separately before consolidation failures are attributed to the new slice.

## Risks / Trade-offs

- **[Hidden-span mapping can be incomplete]** → Quarantine only exact-mapped intervals, report partial coverage for uncertain associations, and never subtract text from a heuristic visual match.
- **[A larger section vocabulary increases false positives]** → Exact aliases establish sections; fuzzy/style evidence is supporting only; unknown headings abstain.
- **[Entry grouping may connect unrelated lines or columns]** → V1 uses explicit bounded source relationships, retains ambiguous spans, and does not infer unsupported PDF columns.
- **[Structured data could accidentally expand scoring authority]** → Keep separate structured-record types; reject new scoring signals/weights; verify visible-input scoring snapshots.
- **[AI and code records may conflict]** → Preserve field authority, require independent evidence, never overwrite code, and surface reviewer uncertainty.
- **[Skill taxonomies are large and contain ambiguous labels]** → Compile only approved languages/fields, require explicit section/token context, version aliases, and measure false-positive precision.
- **[New dependencies increase build and runtime cost]** → Benchmark before adoption, pin versions, avoid pretrained models, and keep Docling out of runtime.
- **[New persisted PII surface]** → Closed schema, bounds, shared sanitizer, redaction defense-in-depth, and dedicated SQLite/API/log leakage fixtures.
- **[Dual-read behavior can diverge]** → Centralize record reconciliation/projection and retain fixture pairs for new and legacy payloads.
- **[Scope becomes a generalized parser rewrite]** → Freeze V1 semantic schemas to education, employment, and explicit skills; detect but do not semantically materialize other categories.

## Migration Plan

1. Record the focused backend/frontend baseline and isolate the known unrelated prompt assertion.
2. Add internal understanding domain types, bounds, sanitizer, serializer, and nullable top-level persistence contract without changing consumers.
3. Add the shared source/presentation index and exact visibility quarantine; route current candidate extraction through exclusions and prove visible-score invariance plus hidden-only correction.
4. Add centralized section/date annotations and stable IDs. Adapt Structural Audit to consume them while preserving its serialized contract byte-for-byte for equivalent visible fixtures.
5. Add the shared entry builder and conservative education/employment/explicit-skills materializers with coverage and field evidence.
6. Add the versioned local ESCO skill-index build/validation path and exact matcher using the current runtime.
7. Add code-owned company/education research-subject projection and union validated AI additions. Keep LinkedIn unchanged.
8. Extend the AI request with bounded understanding context and the masked visible-source projection, then add authority-preserving reconciliation and exclusion-aware response validation.
9. Add dual-read frontend projections and replace new-report date-string joins with stable IDs while keeping legacy fallback.
10. Verify API/SQLite retry/reload/retention/deletion, privacy, limits, backend tests, frontend tests/build, strict OpenSpec validation, and the real local stack.
11. Remove duplicate date/section traversals only after every production consumer uses the shared annotations. Keep compatibility wrappers for one release.

Rollback is additive: stop writing/reading `document_understanding`, restore legacy research/UI projections, and retain the old deterministic/structural/AI payloads. No destructive database migration or legacy fact deletion occurs in V1.

## Open Questions

No implementation-blocking questions remain. Parser-library and matcher-library replacements require separate future changes.
