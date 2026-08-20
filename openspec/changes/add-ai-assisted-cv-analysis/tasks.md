## 1. Slice 0 - Prompt and Eval Baseline

- [x] 1.1 Get project-owner approval for the rescoped proposal, design, and roadmap
- [x] 1.2 Map every Magdalena backlog card to a prompt rule, fixed signal, research check, UI result, or explicit test
- [x] 1.3 Derive an anonymous finding taxonomy, boundaries, and completeness checklist from the private `data/` corpus
- [x] 1.4 Select four CVs for the first eval and record expected findings, accepted unknowns, and unsupported-output checks outside Git
- [x] 1.5 Define versioned Document Analyzer instructions and a strict schema for facts, findings, evidence, uncertainty, and research candidates
- [x] 1.6 Add a local eval command that records recall, unsupported findings, evidence accuracy, latency, tokens, and estimated cost
- [x] 1.7 Test GPT-5.6 Luna with medium reasoning and record the accepted baseline

## 2. Slice 1 - Page-Aware Backend Input

- [ ] 2.1 Make the page model the canonical ingestion source with per-page text, stable page IDs, line order, and exact evidence mapping; derive temporary `lines`, `contact_region`, and `body_region` compatibility views from it
- [ ] 2.2 Generate simple page-separated Markdown without guessed headings, tables, columns, contact regions, or relationships
- [ ] 2.3 Add the approved configurable `minimum_meaningful_tokens` policy with a default of 5 across the whole document, then return distinct empty or scan-only and insufficient-text errors
- [ ] 2.4 Preserve real PDF page boundaries; split DOCX only at explicit author-defined page breaks, treat a DOCX without them as one logical page, and do not infer Word layout or add a rendering service
- [ ] 2.5 Prevent new code from depending on `lines`, `contact_region`, or `body_region`, and document their Slice 1 compatibility-only status
- [ ] 2.6 Test PDF and DOCX boundaries, source fidelity, evidence mapping, zero-token extraction, the one-to-four-token insufficient boundary, the five-token acceptance boundary, the existing sparse CV, and compatibility-view derivation
- [ ] 2.7 Require the existing deterministic unit, API, and report behavior tests to pass unchanged as the Slice 1 completion gate

## 3. Slice 2 - Deterministic Facts and Prototype Cleanup

- [ ] 3.1 Define code-owned fact, candidate, evidence, authority, extractor-version, and reference-data-version types
- [ ] 3.2 Extract phone, email, URL, date, national-ID, and explicit location candidates with exact page evidence and without semantic guessing
- [ ] 3.3 Replace the default-DE phone behavior with explicit international parsing and an unknown result when country assignment needs an assumption
- [ ] 3.4 Replace the prototype gazetteer with versioned offline locality resolution that preserves unresolved and ambiguous outcomes
- [ ] 3.5 Identify the code-owned claimed location without using AI and keep it undetermined when person, employer, office, client, project, or education locations cannot be distinguished deterministically
- [ ] 3.6 Remove spelling locale, currency, date-format locale, email TLD, employer location, and education location as evidence of the candidate's physical location
- [ ] 3.7 Keep right-to-work informational, redact national-ID values before AI formatting or any durable output, and separate organization locations from candidate location
- [ ] 3.8 Restrict scoring inputs to validated code-owned facts and preserve deterministic gray handling when evidence is insufficient
- [ ] 3.9 Replace prototype extractor and scoring fixtures with anonymous cases for ambiguity, international phones, shared postal formats, locality coverage, weak proxies, and deterministic reproducibility
- [ ] 3.10 Return a tested limited deterministic-only report without depending on removed prototype heuristics
- [ ] 3.11 Migrate the remaining legacy consumers to the canonical page/fact model and remove the Slice 1 `lines`, `contact_region`, and `body_region` compatibility views

## 4. Slice 3 - Synchronous AI Base Report

- [ ] 4.1 Add OpenAI settings, secret documentation, a disabled feature flag, request timeout, and pinned GPT-5.6 Luna configuration
- [ ] 4.2 Update the Document Analyzer prompt, schema, and eval input contract for page-aware text plus versioned deterministic observations
- [ ] 4.3 Re-run the four-CV baseline and accept a versioned prompt/schema only after evidence and finding metrics remain within agreed limits
- [ ] 4.4 Call the OpenAI Document Analyzer from the existing pipeline without web tools and validate its schema, page IDs, and exact excerpts
- [ ] 4.5 Keep each CV request independent and reject invalid evidence, unsupported demographic inferences, malformed research candidates, and AI-derived verdict inputs
- [ ] 4.6 Return deterministic contact facts and AI-derived education, employment, relationship, and reviewer findings with explicit authority/source labels
- [ ] 4.7 Return code-owned phone-country, stated-location, and combined outside-EU observations with their limitations
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
