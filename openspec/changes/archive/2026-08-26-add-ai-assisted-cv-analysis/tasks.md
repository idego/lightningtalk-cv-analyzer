## 1. Slice 0 - Prompt and Eval Baseline

- [x] 1.1 Get project-owner approval for the rescoped proposal, design, and roadmap
- [x] 1.2 Map every Magdalena backlog card to a prompt rule, fixed signal, research check, UI result, or explicit test
- [x] 1.3 Derive an anonymous finding taxonomy, boundaries, and completeness checklist from the private `data/` corpus
- [x] 1.4 Select four CVs for the first eval and record expected findings, accepted unknowns, and unsupported-output checks outside Git
- [x] 1.5 Define versioned Document Analyzer instructions and a strict schema for facts, findings, evidence, uncertainty, and research candidates
- [x] 1.6 Add a local eval command that records recall, unsupported findings, evidence accuracy, latency, tokens, and estimated cost
- [x] 1.7 Test GPT-5.6 Luna with medium reasoning and record the accepted baseline

## 2. Slice 1 - Page-Aware Backend Input

- [x] 2.1 Make the page model the canonical ingestion source with per-page text, stable page IDs, line order, and exact evidence mapping; derive temporary `lines`, `contact_region`, and `body_region` compatibility views from it
- [x] 2.2 Generate simple page-separated Markdown without guessed headings, tables, columns, contact regions, or relationships
- [x] 2.3 Add the approved configurable `minimum_meaningful_tokens` policy with a default of 5 across the whole document, then return distinct empty or scan-only and insufficient-text errors
- [x] 2.4 Preserve real PDF page boundaries; split DOCX only at explicit author-defined page breaks, treat a DOCX without them as one logical page, and do not infer Word layout or add a rendering service
- [x] 2.5 Prevent new code from depending on `lines`, `contact_region`, or `body_region`, and document their Slice 1 compatibility-only status
- [x] 2.6 Test PDF and DOCX boundaries, source fidelity, evidence mapping, zero-token extraction, the one-to-four-token insufficient boundary, the five-token acceptance boundary, the existing sparse CV, and compatibility-view derivation
- [x] 2.7 Require the existing deterministic unit, API, and report behavior tests to pass unchanged as the Slice 1 completion gate

## 3A. Slice 2A - Deterministic Facts Foundation

- [x] 3A.1 Define separate `Candidate`, `Fact`, `Observation`, and `ScoringSignal` types behind one `DeterministicAnalysisResult`, with authority, evidence, extractor version, and any applicable reference-data version on every result
- [x] 3A.2 Introduce separate raw-document and redacted-document types; mask national-ID values with same-length replacements before Markdown, AI, persistence, logs, or reports, and derive persistence identity from the redacted canonical-text hash
- [x] 3A.3 Extract phone, email, URL, date, national-ID, postal, and explicit-location candidates with exact page evidence and without semantic guessing
- [x] 3A.4 Implement phone classification and aggregation: keep every phone, retain `possible` as an observation, create a fact only for a `valid` number resolving to one region without a default-region assumption, create one scoring signal only when all resolved countries agree, and otherwise emit an ambiguous non-scoring observation
- [x] 3A.5 Introduce the replaceable `LocationResolver` interface with explicit resolved, unresolved, and ambiguous outcomes
- [x] 3A.6 Build the V1 offline location index from GeoNames `cities500`, `countryInfo`, and `alternateNamesV2` records filtered to identifiers present in the index; treat an absent entry as `unresolved`, never as nonexistent or invalid
- [x] 3A.7 Emit and validate a reference-data manifest containing source names and URLs, snapshot date, SHA-256 values for every input and the built index, index schema version, filtering rules, and record counts; document a quarterly, manually started, reviewed, and approved refresh with no analysis-time download
- [x] 3A.8 Resolve a scoring claim only from an explicit person-location description; retain an unlabeled header place as an observation and keep person, employer, client, project, office, and education locations as separate concepts
- [x] 3A.9 Preserve all existing JSON fields and add one nested `deterministic` field carrying candidates, facts, observations, scoring signals, authority, evidence, and versions through the report and persistence boundaries
- [x] 3A.10 Add anonymous unit, API, privacy, and reference-data tests covering result types, exact evidence, phone validity and conflicts, location ownership and ambiguity, aliases, bounded-index misses, masking, manifest integrity, offline analysis, persistence hashing, and additive JSON compatibility
- [x] 3A.11 Complete Slice 2A only when its new tests and all existing ingestion, deterministic, API, and report tests pass, strict OpenSpec validation and diff checks pass, no scoring weight or threshold changed, and no OpenAI or Slice 3 code or configuration was added

## 3B. Slice 2B - Scoring Cleanup and Legacy Removal

- [x] 3B.1 Remove spelling locale, currency, date-format locale, email TLD, employer location, education location, client location, project location, and office location as evidence of the candidate's physical location
- [x] 3B.2 Keep right-to-work informational and postal compatibility as a zero-weight observation until separate anonymous calibration and project-owner approval authorize a scoring change
- [x] 3B.3 Restrict score and band calculation to `ScoringSignal` values derived by fixed rules from validated code-owned facts, preserving deterministic gray handling for insufficient evidence and excluding AI from the verdict path
- [x] 3B.4 Preserve the configured weights, minimum-evidence rule, and band thresholds; require separate anonymous calibration and explicit project-owner approval before changing any of them
- [x] 3B.5 Replace prototype extractor and scoring fixtures with anonymous cases for ambiguity, multiple international phones, shared postal formats, GeoNames coverage and aliases, unresolved locations, weak proxies, and deterministic reproducibility
- [x] 3B.6 Return and persist a tested deterministic-only report without removed prototype heuristics, using the redacted canonical-text hash as its document identity
- [x] 3B.7 Migrate every remaining consumer to the canonical page-aware fact model, then remove the Slice 1 `lines`, `contact_region`, and `body_region` adapter and the legacy region-splitting path
- [x] 3B.8 Add scoring, report, persistence, API, and regression tests proving that weak or ambiguous observations cannot affect score or band, AI cannot enter scoring, and supported legacy API fields remain compatible
- [x] 3B.9 Complete Slice 2B only when its new tests and the full existing suite pass, strict OpenSpec validation and diff checks pass, legacy-adapter references are absent, weights and thresholds remain unchanged, and Slice 3 remains unstarted

## 4. Slice 3 - Synchronous AI Base Report

- [x] 4.1 Add OpenAI settings, secret documentation, a disabled feature flag, request timeout, and pinned GPT-5.6 Luna configuration
- [x] 4.2 Update the Document Analyzer prompt, schema, and eval input contract for page-aware text, stable page-scoped source-line evidence IDs, code-materialized exact excerpts, and versioned deterministic observations
  - The active v8 model contract is lean: per-field `{value,line_ids}` evidence; code owns excerpts, authority/source, check mapping, checklist counts, and research-candidate derivation.
- [x] 4.3 Re-run the four-CV baseline and accept a versioned prompt/schema only after evidence and finding metrics remain within agreed limits
  - Prompt `3202` with schema `document-analysis-schema-v8` passed the paid GPT-5.6 Luna gate: 100% semantic recall, 100% finding and line evidence accuracy, zero unsupported findings, and two manually reviewed non-`attention` noise findings within the accepted limit of one per two CVs. The run took 78.57 seconds and cost an estimated USD 0.01423.
- [x] 4.4 Call the OpenAI Document Analyzer from the existing pipeline without web tools and validate its schema, page IDs, and exact excerpts
- [x] 4.5 Keep each CV request independent and reject invalid evidence, unsupported demographic inferences, malformed research candidates, and AI-derived verdict inputs
  - Field-level fact validation is partial and fail-closed: invalid optional fields become unknown with a neutral warning while valid facts/findings remain; root/schema, protected-boundary, and unusable finding evidence failures reject the response.
- [x] 4.6 Return deterministic contact facts and AI-derived education, employment, relationship, and reviewer findings with explicit authority/source labels
- [x] 4.7 Return code-owned phone-country, stated-location, and combined outside-EU observations with their limitations
- [x] 4.7a Add a reviewed, versioned, official-source-backed catalog of common public mail-provider domains and legitimate aliases covering major international families (Google, Microsoft, Yahoo, Proton, Apple, and Zoho) and common Polish providers (Onet, WP/o2, and Interia); emit a code-owned, zero-weight `possible_email_domain_typo` observation only for conservative close confusable spellings such as `gmail.cm`, with exact evidence, catalog provenance, a confirmation caveat, no custom-domain inference, and regression tests
- [x] 4.8 Store AI findings, importance, confidence, evidence, authority, deterministic-observation version, model versions, usage, and audit data in SQLite
- [x] 4.9 Merge AI findings into the report without changing deterministic score, band, facts, or rule findings
- [x] 4.10 Return a stable analysis ID and the complete flag checklist as JSON
  - Every code Observation is also exposed as a code-owned remaining flag for `Pozostałe sygnały`.
- [x] 4.11 Show `Wymaga uwagi`, `Warto wiedzieć`, and collapsed `Pozostałe sygnały` in the HTML UI
  - The UI shows the neutral partial-validation warning without hiding accepted output.
- [x] 4.12 Set and document a measured V1 limit for the existing sequential batch endpoint
- [x] 4.13 Test the full single-CV and bounded-batch flow in the backend, frontend, deterministic suite, and four-CV eval
  - The completed gate covers single-CV and four-file fake-client HTTP flows, SQLite migration and audit equality, deterministic byte-invariance, 375 backend tests, frontend grouping tests, typecheck, changed-file lint, a Docker production build, the accepted four-CV Luna eval, and one held-out DOCX through the running web-to-API Compose path with AI enabled. The held-out report completed in 31.6 seconds with structured contact, education, employment, and reviewer findings.

## 5. Slice 4 - Synchronous Company Research

- [x] 5.1 Let the recruiter start company research for a stored analysis
- [x] 5.2 Add an idempotent company-research endpoint with a bounded timeout
- [x] 5.3 Define the Web Search prompt and schema for company existence, dates, activity, location, employer/client/project relations, websites, company pages, and registries
- [x] 5.4 Store cited findings, confidence, access time, usage, and completed result in SQLite
- [x] 5.5 Show company research without changing score or band
- [x] 5.6 Show the requested limited-online-presence flag with the searches performed and their limits
- [x] 5.7 Test sources, uncertainty, prompt injection, timeout, retry, duplicate requests, and cost limits

## 6. Slice 5 - Synchronous Education and Certification Research

- [x] 6.1 Let the recruiter start education and certification research for a stored analysis
- [x] 6.2 Add an idempotent education-research endpoint with a bounded timeout
- [x] 6.3 Define the Web Search prompt and schema for institutions, programs, degrees, certificates, dates, accreditation, city, and country
- [x] 6.4 Store cited results in SQLite and highlight institution-country differences from the current code-owned stated location for review without affecting score or band
- [x] 6.5 Show education research separately from company and LinkedIn results
- [x] 6.6 Test evidence, uncertainty, timeout, retry, duplicate requests, and cost limits

## 7. Slice 6 - Synchronous LinkedIn Discovery and Manual Review

- [x] 7.1 Let the recruiter start candidate-scoped LinkedIn discovery for a stored analysis
- [x] 7.2 Add an idempotent LinkedIn-discovery endpoint with a bounded timeout
- [x] 7.3 Return possible profiles with cited public-result evidence and discovery confidence without claiming identity or comparing them with the CV
- [x] 7.4 Report visible photo and connection-count availability and apply the agreed completeness threshold without analyzing appearance
- [x] 7.5 Show a `linkedin_not_found` flag with the searches performed and their limitations
- [x] 7.6 Expose every possible profile as a separate manual-review link without a confirmation endpoint
- [x] 7.7 Prohibit automated profile-to-CV comparison in discovery and omit the comparison flow from the API and UI
- [x] 7.8 Test wrong-person matches, ambiguity, no profile, evidence, timeout, retry, and candidate isolation

## 8. Slice 7 - V1 Hardening in the Existing Architecture

- [x] 8.1 Add versioned SQLite cache entries for reusable company, institution, program, and certificate research
- [x] 8.2 Reuse cache entries without leaking candidate data and record cache use in the audit
- [x] 8.3 Measure single-CV and realistic-batch latency, request failures, token use, and cost
  - Live local Docker measurements cover one held-out single CV and one two-file batch: three successful CVs, zero failures, 58.53 seconds across the two HTTP requests, 11,738 input tokens, 6,441 output tokens, and estimated cost USD 0.010077. The accepted four-case eval adds 78.57 seconds and estimated USD 0.014226.
- [x] 8.4 Set request timeout, batch size, retry, search, and cost limits from measurements
  - Keep the measured V1 limits at 120 seconds per model request, zero automatic retries, four files and 20 MiB per batch, four Web Search calls per research action, and 4,096 output tokens. Local validation uses a USD 1 soft budget and USD 2 hard stop; production must add a provider-side project budget rather than pretending a post-response application check can prevent spend.
- [x] 8.5 Verify original-file deletion, national-ID redaction, development retention, and the approved production retention
  - Uploads remain request-scoped and are never persisted as original files; national-ID API, database, audit, batch and log privacy tests pass. One runtime-configurable value covers the complete candidate-analysis graph, defaults to 90 days in development, persists when changed in Settings, and replaces the rejected idea of a separate hard-coded production value. Reusable public-entity cache entries keep their independent non-candidate TTL.
- [x] 8.6 Add request metrics, structured logs, research error reporting, cache metrics, and an operations guide
- [x] 8.9 Create a separate architecture proposal only if measured volume or failures require background processing
  - The measured local single and batch flows completed without failures and do not justify a queue, workers, leases, polling, or a new database. No separate architecture proposal is created for V1.
- [x] 8.10 Require the approved GeoNames pair in the standard development stack, fail startup instead of silently degrading, and expose non-sensitive capability readiness through health
- [x] 8.11 Add Settings navigation with independent English/Polish UI and AI-report language controls plus a complete capability health check
- [x] 8.12 Replace batch submission with sequential per-file requests, honest progress using one Thinking Orb, isolated errors, and incremental results
- [x] 8.13 Add a compact multi-CV report workspace with grouped visible findings and a hideable, resizable, independently scrolling original-file preview synchronized to the dominant report
- [x] 8.14 Treat unlabelled CV phone numbers as candidate-owned unless explicitly attributed to another person or organization; preserve all numbers and expose cross-country ambiguity without changing configured weights

## 9. HR Acceptance Follow-ups

- [x] 9.1 Prevent digits inside extracted email spans from becoming phone candidates, facts, observations, or scoring signals; cover the public deterministic pipeline and API seam with anonymous tests
  - Candidate extraction excludes every phone-shaped span that overlaps a syntactically extracted email. Deterministic and HTTP assertions remain in the regression suite; Docker-hosted FastAPI `TestClient` execution is working.
- [x] 9.2 Tighten the `document_artifact` policy so understandable extraction defects are suppressed and only meaning-blocking defects remain; cover the validated AI contract with anonymous tests
  - Prompt policy requires an important blocked fact or changed meaning. Code suppresses findings unless exact source evidence contains a language-neutral strong corruption marker; ordinary joined words, spacing, wrapping, or repeated structure remain limitations.
- [x] 9.3 Add safe failure stages and configurable bounded retries with defaults of one transport retry, one invalid-response retry, and three total attempts; preserve 120 seconds, 4,096 output tokens, deterministic fallback, per-file isolation, and log/persistence privacy
  - The OpenAI SDK remains at zero retries. Application policy classifies timeout/network/429/5xx as retryable transport, rejects other 4xx retries, permits one invalid-response retry, and enforces the absolute attempt cap. API/audit diagnostics are additive and content-free.
- [x] 9.4 Add a manual AI Retry action that retains the deterministic report and uses non-technical unavailable copy
  - Owner-scoped Retry calls only Document Analyzer against a redacted process-memory context, preserves deterministic and completed research payloads, coalesces concurrent attempts, and removes context after success, deletion, retention cleanup, or restart.
- [x] 9.5 Add code-owned plain-language templates for known findings with `What we found`, `Why it matters`, and `What to check`, and hide technical labels as primary UI explanations
  - The presentation layer keeps source facts/evidence unchanged, maps known deterministic categories to English B2 copy, uses selected-language AI prose as the fallback, simplifies English timeline-overlap notes, and removes category, rule, authority, confidence, extractor, reference-data, and raw contact-kind labels from the main view.
- [x] 9.6 Add Analysis settings with a master automatic-public-research toggle plus independent company, education, and LinkedIn discovery toggles; show active categories at upload and run post-analysis research with bounded concurrency and independent status
- [x] 9.7 Keep LinkedIn discovery manual-review only in both explicit and automatic flows, with no confirmation or profile-to-CV comparison action
- [x] 9.8 Document and regression-test the neutral candidate-name boundary: name is a fact only and never a proxy, suspicious finding, score, or band input
  - The name-only mutation regression keeps the complete deterministic payload, findings, checklist counts, score, band, and research-category eligibility unchanged; only the neutral name fact and candidate-scoped LinkedIn query subject differ.
- [x] 9.9 Prepare a concrete calibration proposal for a 0-100 score and green/amber/red/gray bands from the acceptance set; keep failed/incomplete/insufficient gray and do not change `weights.yaml`, thresholds, or runtime band logic without a separate checkpoint
  - `docs/scoring-calibration-proposal.md` defines candidate code-owned categories, independence/deduplication, coverage, weights, bands, anonymous scenarios, the 16-CV calibration method, rejection gates, and the remaining owner decisions without changing runtime scoring.
- [x] 9.10 Run one focused P0/P1/P2 review after each logical implementation stage
  - Focused reviews and independent verification closed the implementation findings; rollout and stakeholder decisions are intentionally outside this change.
- [x] 9.11 Deduplicate recruiter-facing flags, aggregate repeated outside-EU conclusions, and keep distinct supporting details available
- [x] 9.12 Add the structured CV overview, deterministic education and experience date summaries, whole-card disclosure interaction, honest empty-section affordances, separate LinkedIn profile cards, and left-aligned Back navigation
- [x] 9.13 Apply the project-owner-approved small-locality threshold below 10,000 and preserve the intended education-country difference as a zero-weight manual-review signal
