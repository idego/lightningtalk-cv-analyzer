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
- [ ] 4.3 Re-run the four-CV baseline and accept a versioned prompt/schema only after evidence and finding metrics remain within agreed limits
  - Prompt `3108` is frozen as the current implementation contract, but its four-case GPT-5.6 Luna baseline is not accepted: two responses failed the fail-closed evidence/checklist validation. Final model/prompt acceptance returns in the 4.13 model gate; metrics remain unchanged.
- [x] 4.4 Call the OpenAI Document Analyzer from the existing pipeline without web tools and validate its schema, page IDs, and exact excerpts
- [x] 4.5 Keep each CV request independent and reject invalid evidence, unsupported demographic inferences, malformed research candidates, and AI-derived verdict inputs
- [x] 4.6 Return deterministic contact facts and AI-derived education, employment, relationship, and reviewer findings with explicit authority/source labels
- [x] 4.7 Return code-owned phone-country, stated-location, and combined outside-EU observations with their limitations
- [x] 4.7a Add a reviewed, versioned, official-source-backed catalog of common public mail-provider domains and legitimate aliases covering major international families (Google, Microsoft, Yahoo, Proton, Apple, and Zoho) and common Polish providers (Onet, WP/o2, and Interia); emit a code-owned, zero-weight `possible_email_domain_typo` observation only for conservative close confusable spellings such as `gmail.cm`, with exact evidence, catalog provenance, a confirmation caveat, no custom-domain inference, and regression tests
- [ ] 4.8 Store AI findings, importance, confidence, evidence, authority, deterministic-observation version, model versions, usage, and audit data in SQLite
- [ ] 4.9 Merge AI findings into the report without changing deterministic score, band, facts, or rule findings
- [ ] 4.10 Return a stable analysis ID and the complete flag checklist as JSON
- [ ] 4.11 Show `Wymaga uwagi`, `Warto wiedzieć`, and collapsed `Pozostałe sygnały` in the HTML UI
- [ ] 4.12 Set and document a measured V1 limit for the existing sequential batch endpoint
- [ ] 4.13 Test the full single-CV and bounded-batch flow in the backend, frontend, deterministic suite, and four-CV eval

## 5. Slice 4 - Synchronous Company Research

- [ ] 5.1 Let the recruiter start company research for a stored analysis
- [ ] 5.2 Add an idempotent company-research endpoint with a bounded timeout
- [ ] 5.3 Define the Web Search prompt and schema for company existence, dates, activity, location, employer/client/project relations, websites, company pages, and registries
- [ ] 5.4 Store cited findings, confidence, access time, usage, and completed result in SQLite
- [ ] 5.5 Show company research without changing score or band
- [ ] 5.6 Show the requested limited-online-presence flag with the searches performed and their limits
- [ ] 5.7 Test sources, uncertainty, prompt injection, timeout, retry, duplicate requests, and cost limits

## 6. Slice 5 - Synchronous Education and Certification Research

- [ ] 6.1 Let the recruiter start education and certification research for a stored analysis
- [ ] 6.2 Add an idempotent education-research endpoint with a bounded timeout
- [ ] 6.3 Define the Web Search prompt and schema for institutions, programs, degrees, certificates, dates, accreditation, city, and country
- [ ] 6.4 Store cited results in SQLite and highlight unexplained location differences for review
- [ ] 6.5 Show education research separately from company and LinkedIn results
- [ ] 6.6 Test evidence, uncertainty, timeout, retry, duplicate requests, and cost limits

## 7. Slice 6 - Synchronous LinkedIn Discovery and Comparison

- [ ] 7.1 Let the recruiter start candidate-scoped LinkedIn discovery for a stored analysis
- [ ] 7.2 Add an idempotent LinkedIn-discovery endpoint with a bounded timeout
- [ ] 7.3 Return possible profiles with match evidence and confidence without claiming identity
- [ ] 7.4 Report visible photo and connection-count availability and apply the agreed completeness threshold without analyzing appearance
- [ ] 7.5 Show a `linkedin_not_found` flag with the searches performed and their limitations
- [ ] 7.6 Require recruiter confirmation before profile-to-CV comparison
- [ ] 7.7 Compare a confirmed profile's companies, roles, dates, location, and education with the CV
- [ ] 7.8 Test wrong-person matches, ambiguity, no profile, evidence, timeout, retry, and candidate isolation

## 8. Slice 7 - V1 Hardening in the Existing Architecture

- [ ] 8.1 Add versioned SQLite cache entries for reusable company, institution, program, and certificate research
- [ ] 8.2 Reuse cache entries without leaking candidate data and record cache use in the audit
- [ ] 8.3 Measure single-CV and realistic-batch latency, request failures, token use, and cost
- [ ] 8.4 Set request timeout, batch size, retry, search, and cost limits from measurements
- [ ] 8.5 Verify original-file deletion, national-ID redaction, development retention, and the approved production retention
- [ ] 8.6 Add request metrics, structured logs, research error reporting, cache metrics, and an operations guide
- [ ] 8.7 Run the wider permitted corpus regression and agree on acceptance criteria with HR
- [ ] 8.8 Get stakeholder acceptance, enable the feature, and keep a tested deterministic-only rollback based on the new code-owned facts
- [ ] 8.9 Create a separate architecture proposal only if measured volume or failures require background processing
