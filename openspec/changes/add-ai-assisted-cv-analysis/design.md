## Context

The application already has a clear top-level architecture: Next.js authenticates the user and proxies uploads to FastAPI; FastAPI calls a library-first Python pipeline; the pipeline parses PDF or DOCX, builds a report, and stores audit data in SQLite. Docker Compose runs `web` and `api`.

The V1 keeps these service boundaries and external requests, but it may replace prototype internals. In particular, the current flattened document model, contact/body heuristic, weak location proxies, and first-match extractors are not architectural constraints. AI document analysis runs inside the existing analysis request. Optional company, education, and LinkedIn checks run through separate synchronous requests to the same API. We accept the latency and sequential batch behavior for the first version, then measure them.

The rules in `AGENTS.md` still apply. The product supports human review. It does not verify identity or location and does not make hiring decisions. The score and four bands remain deterministic. The system redacts national-ID values. The approved OpenAI account can process candidate data. The private `data/` corpus stays gitignored and is never a runtime input.

## Goals / Non-Goals

**Goals:**

- Add every business check from Magdalena's HR backlog.
- Return a useful AI-assisted report from the existing API flow.
- Give code and AI non-overlapping authority: code owns deterministic facts and verdict inputs; AI owns semantic document interpretation and reviewer findings.
- Remove or replace prototype rules that create unsupported location inferences.
- Keep each candidate in a fresh model context.
- Let recruiters choose which public-web checks use time and money.
- Keep evidence, configuration, audit data, and deterministic scoring clear and testable.
- Measure latency, cost, failure rate, and practical batch limits before proposing infrastructure changes.

**Non-Goals:**

- Add a broker, durable background queue, worker service, leases, heartbeats, or progressive polling.
- Promise unlimited or highly concurrent batches in V1.
- Replace SQLite or change the current Compose service boundaries.
- Support Anthropic or add a provider abstraction.
- Add OCR for image-only CVs.
- Use browser automation, authenticated LinkedIn access, or private data scraping.
- Verify identity or automate a hiring decision.
- Add Tinder-style CV review.
- Preserve every current extractor, internal type, or weak scoring signal.
- Let an AI-derived value become an input to the deterministic score or band.

## Decisions

### D1: Keep the architecture and replace inaccurate internals

Keep the deployable architecture and synchronous request path. Use one staged analysis pipeline:

```text
Next.js -> FastAPI -> page-aware ingestion -> deterministic facts/observations
                                                   |-> deterministic score
                                                   |-> OpenAI Document Analyzer
                                               validated merged report -> SQLite
```

The OpenAI call is another application service used by `pipeline.py`. It is not a new deployable service. Internal ingestion, extraction, report, and persistence types may be replaced. The existing single and batch endpoints remain synchronous.

### D2: Keep `pdfplumber` and use simple Markdown

Keep faithful per-page source text, stable page IDs, line order, and enough source mapping to validate exact excerpts. The formatter adds page separators. It does not guess headings, tables, columns, contact regions, or relationships. Code may detect explicit contact candidates, but ingestion does not need to preserve the current heuristic contact/body split.

For PDF, each extracted PDF page remains one source page with its real boundary. For DOCX, ingestion starts a new logical page only at an explicit page-break construct authored in the document. A DOCX without explicit page breaks is one logical page. The backend does not infer Word's rendered pagination, use stale rendered-page markers, convert DOCX to PDF, or add a rendering service.

The page model is the canonical ingestion source. During Slice 1, `lines`, `contact_region`, and `body_region` remain temporary compatibility views derived from that model so the existing deterministic pipeline and tests continue to run without behavior changes. New code must consume pages or explicit source-mapped candidates rather than depend on those views. Slice 2 migrates the remaining legacy consumers and removes the compatibility views.

Text sufficiency uses a conservative, configurable document-level policy. The accepted default is `minimum_meaningful_tokens: 5`, counted across the whole document after Unicode and whitespace normalization. A meaningful token has at least two characters after surrounding punctuation is removed and contains at least one Unicode letter. Page separators, whitespace, punctuation-only fragments, and isolated one-character extraction artifacts do not count. Zero meaningful tokens remains an empty or scan-only extraction error. One to four meaningful tokens produces the distinct insufficient-text error. Five or more passes ingestion, including sparse CVs whose evidence may still produce a deterministic gray result or AI unknown states.

We rejected PDF Inspector as the default. In the corpus test, it made cleaner Markdown but damaged more text, links, and column relationships. Direct PDF input can remain a future eval, but it is not the baseline.

### D3: Separate deterministic authority from semantic interpretation

Before the model call, code extracts mechanically recognizable candidates and validates what it can without semantic guessing. The deterministic core uses separate `Candidate`, `Fact`, `Observation`, and `ScoringSignal` types and returns them through one `DeterministicAnalysisResult`. Examples include phone-shaped strings, email and URL syntax, date tokens, national-ID presence/type, and unambiguous offline location matches.

Every deterministic result records its authority, exact page evidence, and extractor version. A result that depends on reference data also records the applicable reference-data version. `Candidate` records recognizable source content without asserting that it is true or scoreable. `Fact` records only a mechanically validated, code-owned value. `Observation` records unresolved, ambiguous, invalid, possible, or informational outcomes. `ScoringSignal` is created from validated facts by a fixed scoring rule; candidate extractors do not assign weights.

Only code-owned facts may enter score and band calculation. An ambiguous claimed location, phone, postal pattern, or locality remains unknown for scoring. AI may explain the ambiguity for a reviewer but cannot fill a missing verdict input.

The Document Analyzer receives both the complete page-aware CV after required national-ID redaction and the versioned deterministic observations. It owns semantic tasks such as associating organizations, roles, dates, locations, education entries, relationship types, internal conflicts, document artifacts, and research candidates. The full redacted CV remains present so an incomplete candidate extractor cannot hide content from the model. Raw national-ID values never enter the model request, report, logs, audit, or persistence. The ingestion boundary distinguishes a raw document from a redacted document. National-ID spans are replaced with same-length masks before Markdown or any downstream output, which preserves page offsets without retaining the source value. Persistence receives a hash of redacted canonical text rather than raw file bytes.

The model cites evidence through stable page-scoped source-line IDs rather than
copying candidate text. After the model call, code validates the schema, page
and line IDs, materializes exact excerpts from the canonical redacted source,
and validates protected boundaries and consistency between returned values and
evidence. Unknown, cross-page, or mismatched line references fail closed. This
keeps the final report source-exact without accepting whitespace normalization,
reordered fragments, or model-authored evidence text. Deterministic date
arithmetic or other checks over AI-extracted semantic facts remain AI-assisted
findings and stay outside the score.

### D4: Make one bounded OpenAI call per CV

Use the OpenAI Responses API and GPT-5.6 Luna. Start with medium reasoning and strict structured output. Send one complete page-aware CV after required national-ID redaction, its versioned deterministic observations, and versioned instructions. Do not enable web tools. Return structured semantic facts, findings, evidence, uncertainty, and research candidates.

Each call starts without a previous response or another candidate's context. The current batch endpoint can call this flow sequentially. V1 documents and enforces a practical batch limit based on measured request duration.

The synchronous V1 batch limit is four files and 20 MiB of combined readable
upload data by default. Both values are configurable and are checked before any
CV analysis starts. The file cap matches the only current end-to-end batch
measurement: four sequential Luna calls took about 97.5 seconds in total
(about 24.4 seconds per CV on average). This is a conservative development
boundary rather than a latency guarantee; one model request may still run until
the fixed 120-second timeout. Raising the cap requires later production-volume
measurements, not a queue or service-boundary change in this slice.

### D5: Keep AI outside the verdict

Only code-owned facts and fixed rules can change the score and band. Neither AI findings nor AI-selected facts may become verdict inputs. AI findings have separate `importance` and `confidence` values. The UI can highlight an important finding, but the finding cannot change weights or bands.

Requested weak signals remain visible. For example, the report can flag that no LinkedIn profile was found, a profile has no visible photo or sufficient public connection count, or a company has little detectable online presence. It must also show the evidence and search limits.

### D6: Remove weak location proxies from the verdict

The deterministic core keeps valid international phone-country parsing, explicitly person-owned claimed-location resolution, offline locality lookup, national-ID redaction, and other facts that can be reproduced from source evidence. It does not score spelling locale, currency, date-format locale, email TLD, education location, employer location, or postal compatibility as evidence of the candidate's location. Right-to-work statements may remain informational but never prove physical location or eligibility.

Phone-shaped values that libphonenumber considers only possible remain observations. Only a valid international number that maps to one region can create a phone-country fact. The system preserves all detected phone candidates and facts. It creates one phone scoring signal only when all deterministically person-owned, country-resolved phone facts agree. Conflicting resolved countries create an ambiguous observation and no phone scoring signal. Numbers without an international prefix do not receive a guessed default country.

A syntactically valid email domain is not automatically trustworthy or wrong.
Code may compare it with a reviewed, versioned reference catalog of common
public mail-provider domains and their legitimate aliases. The initial catalog
shall cover major international provider families such as Google, Microsoft,
Yahoo, Proton, Apple, and Zoho, plus common Polish providers such as Onet,
Wirtualna Polska/o2, and Interia. Catalog entries require an official provider
source and review; the catalog is intentionally maintainable rather than
presented as a complete list of every mailbox provider. A non-scoring
possible-typo observation may be emitted only for a close confusable spelling
of a catalog entry. The observation names the literal similarity and asks the
recruiter to confirm the address. It never claims that the domain, mailbox,
person, or CV is fake, invalid, or nonexistent. Exact catalog domains and
arbitrary company or custom domains do not produce this observation. Email TLD
or provider choice remains excluded from physical-location evidence and
scoring.

Only an explicitly described person location may become the code-owned claimed location used by scoring. An unlabeled place name in the document header remains an observation. Candidate, employer, client, project, office, and education locations are separate concepts and are never collapsed into one location relation. Ambiguous postal formats and locations remain unknown. Postal compatibility stays unweighted until anonymous fixtures, calibration, and project-owner approval support a scoring change.

V1 uses a versioned EU-27 ISO-2 member-state set sourced from the official European Union country list. Phone-country and stated-location outside-EU observations remain separate. A combined observation requires both distinct code-owned categories and both must be non-EU; mixed EU/non-EU categories are reported separately. These observations do not establish nationality, identity, physical presence, work eligibility, or fraud. There is no approved anonymous calibration for locality size or atypicality, so V1 does not classify either. A resolved non-EU locality receives only a `small_locality_not_evaluated` informational checklist result.

The weights-file version and scoring-policy version are separate immutable identities. A report records both, and persistence records their canonical composition, so an algorithm change cannot silently reuse the same weights-only audit identity.

### D7: Run optional research through normal API requests

Document analysis and fixed rules create the base report. Research does not start by default. The recruiter can start company, education/certification, or LinkedIn research separately.

Each button calls a dedicated FastAPI endpoint. The request validates stored research candidates, checks SQLite cache where allowed, calls OpenAI Web Search, validates the structured result, stores it, and returns the updated category. The frontend shows a loading state until that request succeeds or fails.

There is no background job state in V1. If a request fails or the page closes, the user can retry it. Completed writes are idempotent per analysis, category, and research version.

### D8: Use hosted Web Search in read-only mode

Research uses OpenAI Web Search and keeps its source data. It does not use browser automation or logged-in sessions. Treat all page content as untrusted data. A page cannot change the request's instructions, tools, or scope.

LinkedIn discovery returns possible profiles. The recruiter must confirm a possible profile before a later comparison treats its differences from the CV as relevant.

### D9: Keep the existing runtime and persistence

Docker Compose continues to run `web` and `api`. Only `web` publishes a host port. The API stores reports, research results, prompt versions, usage, and audit records in SQLite.

Each accepted base analysis receives one opaque UUID. The same ID links the
HTTP report, deterministic report row, AI-analysis row, and audit row. Existing
SQLite databases are migrated additively: old report and audit rows receive a
stable `legacy-<row id>` identifier and remain readable. The AI row stores the
validated AI payload, importance, confidence, exact evidence, authority,
prompt/schema/input/deterministic-observation versions, configured and response
model names, usage, and safe failure state. It never stores raw file bytes or a
raw national-ID value.

Cache company, institution, program, and certification results in SQLite by normalized entity, research version, and freshness window. Keep source and retrieval data on cache hits. Keep LinkedIn results scoped to one candidate.

The deterministic persistence boundary receives the completed report and the hash of redacted canonical text. It does not receive raw file bytes for fingerprinting. Existing JSON fields remain compatible, and the API adds one nested `deterministic` object containing facts, observations, authority, evidence, extractor versions, and applicable reference-data versions.

### D10: Treat the HR backlog as required product scope

The system must extract contact, education, and employment data; produce the requested phone and location signals; check companies, education, and LinkedIn; and return a complete per-candidate checklist in JSON and HTML.

The report names each observed signal precisely. It does not turn a missing profile, foreign location, low public footprint, name, photo, or other proxy into proof of fraud, nationality, identity, or physical location.

### D11: Build prompts and evals from private corpus lessons

Use the private corpus during development to create an anonymous finding taxonomy, completeness checklist, prompt, schema, and eval set. Never copy raw CVs or HR comments into tracked files or runtime images.

Start with four CVs. Measure expected-finding recall, unsupported findings, evidence accuracy, latency, tokens, and cost. Re-run the baseline after the Document Analyzer input changes from document-only text to page-aware text plus deterministic observations. Use the full permitted corpus only for broader regression testing.

Prompt `3108` is frozen as the current implementation contract while the
remaining Slice 3 integration is built behind the disabled feature flag. Its
four-case GPT-5.6 Luna baseline is not accepted: two responses failed the
fail-closed evidence or checklist validation. This model-quality result does
not weaken validation and does not enable the feature. Final prompt/model
acceptance returns as part of the full Slice 3 gate in task 4.13.

### D12: Use a replaceable offline location resolver

Deterministic location resolution uses a `LocationResolver` interface. The V1 implementation reads a project-built offline index derived from the official GeoNames `cities500`, `countryInfo`, and `alternateNamesV2` downloads. The build keeps only alternate-name records whose GeoNames identifiers are present in the selected city and country index.

`cities500` is a bounded worldwide city dataset, not a complete register of every locality. Absence from the index always produces `unresolved`; it never produces `nonexistent`, `invalid`, or an equivalent verification claim. One matching country interpretation may produce a resolved fact. Multiple matching country interpretations produce an ambiguous observation and no scoring country.

Each built index has a manifest containing at least:

- source file names and URLs;
- snapshot date;
- SHA-256 values for every input file and the built index;
- index schema version;
- filtering rules;
- record counts.

Reference data is refreshed quarterly through a manually started, reviewed, and approved build. The application loads the approved versioned artifact locally and never downloads or updates GeoNames data during CV analysis.

### D13: Deliver Slice 2 as two vertical stages

Slice 2A adds the deterministic types, raw/redacted document boundary, national-ID masking, phone handling, `LocationResolver`, the versioned GeoNames index and manifest, claimed-location rules, and the additive nested deterministic report. It connects these results through the existing synchronous report path and has its own deterministic, privacy, API-compatibility, and reference-data tests.

Slice 2B removes weak scored signals, keeps postal compatibility unweighted, restricts scoring to validated code-owned facts through `ScoringSignal`, replaces prototype fixtures, migrates the remaining canonical-page consumers, and removes the Slice 1 `lines`, `contact_region`, and `body_region` adapter. It has its own scoring, report, persistence, API, and regression tests.

Neither stage changes signal weights, minimum evidence requirements, or band thresholds without separate anonymous calibration and explicit project-owner approval. Slice 3, OpenAI integration, prompt changes, and model calls remain outside both Slice 2 stages.

## Risks / Trade-offs

- [Requests take longer] -> Show clear loading states, set explicit timeouts, measure latency, and set a practical V1 batch limit.
- [A request fails after work starts] -> Store results only after validation and make the user-triggered research action safe to retry.
- [The API process restarts] -> Accept loss of in-flight work in V1; completed reports remain in SQLite.
- [AI misses findings] -> Use corpus-based evals, a completeness checklist, explicit unknowns, and versioned prompts.
- [AI invents a finding] -> Require a CV excerpt or web source and validate every structured result.
- [A prototype rule creates false certainty] -> Remove weak proxy signals, keep ambiguous values unknown, and cover each code-owned fact with anonymous deterministic fixtures.
- [An AI-selected fact changes the verdict] -> Tag fact authority and reject AI-derived score inputs at the scoring boundary.
- [Research matches the wrong person] -> Show uncertainty and require recruiter confirmation for LinkedIn comparison.
- [Research costs grow] -> Make it optional, limit searches, remove duplicate requests, and cache reusable public entities in SQLite.
- [A web page injects instructions] -> Give research read-only tools and treat page text only as data.
- [Private corpus enters Git] -> Keep `data/` ignored and commit only anonymous rules and tests.
- [A requested weak signal is overinterpreted] -> Keep the signal visible, name the observed fact precisely, show its limits, and leave the conclusion to the recruiter.
- [V1 cannot handle required volume] -> Record batch duration and failure data, then propose only the smallest approved infrastructure change supported by measurements.

## Migration Plan

1. Keep the current service boundaries and synchronous endpoints.
2. Replace the flattened input model with page-aware source text and exact evidence mapping.
3. Complete Slice 2A: add the typed deterministic result, redaction boundary, phone and location resolution, approved GeoNames index, and additive `deterministic` report object without changing existing JSON fields.
4. Complete Slice 2B: remove weak verdict proxies, keep postal compatibility unweighted, enforce the scoring boundary, replace fixtures, migrate legacy consumers, and remove the Slice 1 compatibility adapter.
5. Do not change weights or thresholds during Slice 2 without separate calibration and project-owner approval.
6. Update the prompt, schema, and four-CV eval for page-aware redacted text plus versioned deterministic observations only after Slice 2 is complete and Slice 3 is explicitly started.
7. Add the bounded synchronous OpenAI call and validate all AI output.
8. Merge deterministic facts, AI findings, and audit metadata into one report model and SQLite audit.
9. Update the frontend to show the completed AI-assisted report.
10. Add company, education, and LinkedIn research as separate synchronous actions.
11. Add SQLite cache, request limits, retention checks, metrics, and an operations guide.
12. Measure realistic batches and get stakeholder acceptance before enabling the feature.

Disabling AI and research must preserve a tested deterministic-only report based on the new code-owned facts. It does not need to preserve removed prototype heuristics. A queue, workers, or database migration require a separate change proposal and stakeholder approval.

## Open Questions

- Which GPT-5.6 Luna snapshot and reasoning level pass the four-CV eval?
- Which per-CV and per-batch cost limits should production enforce?
- How long should SQLite research cache entries remain valid?
- Which retention period should replace the 90-day development value?
- What configured threshold should the LinkedIn profile-completeness signal use?
