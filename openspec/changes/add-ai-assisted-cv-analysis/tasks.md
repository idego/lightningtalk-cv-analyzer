## 1. Slice 0 - Prompt and Eval Baseline

- [x] 1.1 Get project-owner approval for the rescoped proposal, design, and roadmap
- [x] 1.2 Map every Magdalena backlog card to a prompt rule, fixed signal, research check, UI result, or explicit test
- [x] 1.3 Derive an anonymous finding taxonomy, boundaries, and completeness checklist from the private `data/` corpus
- [x] 1.4 Select four CVs for the first eval and record expected findings, accepted unknowns, and unsupported-output checks outside Git
- [x] 1.5 Define versioned Document Analyzer instructions and a strict schema for facts, findings, evidence, uncertainty, and research candidates
- [x] 1.6 Add a local eval command that records recall, unsupported findings, evidence accuracy, latency, tokens, and estimated cost
- [x] 1.7 Test GPT-5.6 Luna with medium reasoning and record the accepted baseline

## 2. Slice 1 - Page-Aware Input

- [ ] 2.1 Keep per-page source text and page IDs while preserving current normalized lines and contact/body regions
- [ ] 2.2 Generate simple page-separated Markdown without guessed headings, tables, columns, or relationships
- [ ] 2.3 Detect insufficient text and return a clear error for scan-only inputs
- [ ] 2.4 Test PDF and DOCX page boundaries, current normalization, and insufficient-text errors

## 3. Slice 1 - Synchronous AI Base Report

- [ ] 3.1 Add OpenAI settings, secret documentation, a disabled feature flag, request timeout, and pinned GPT-5.6 Luna configuration
- [ ] 3.2 Call the OpenAI Document Analyzer from the existing pipeline without web tools and validate its schema
- [ ] 3.3 Keep each CV request independent and reject invalid evidence, unsupported demographic inferences, and malformed research candidates
- [ ] 3.4 Return structured contact, education, and employment data with source evidence
- [ ] 3.5 Add phone-country, stated-location, and combined outside-EU flags with their limitations
- [ ] 3.6 Store AI findings, importance, confidence, evidence, versions, usage, and audit data in SQLite
- [ ] 3.7 Add AI findings to the report without changing deterministic score, band, or rule findings
- [ ] 3.8 Return a stable analysis ID and the complete flag checklist as JSON
- [ ] 3.9 Show `Wymaga uwagi`, `Warto wiedzieć`, and collapsed `Pozostałe sygnały` in the HTML UI
- [ ] 3.10 Set and document a measured V1 limit for the existing sequential batch endpoint
- [ ] 3.11 Test the full single-CV and bounded-batch flow in the backend, frontend, and four-CV eval

## 4. Slice 2 - Synchronous Company Research

- [ ] 4.1 Let the recruiter start company research for a stored analysis
- [ ] 4.2 Add an idempotent company-research endpoint with a bounded timeout
- [ ] 4.3 Define the Web Search prompt and schema for company existence, dates, activity, location, employer/client/project relations, websites, company pages, and registries
- [ ] 4.4 Store cited findings, confidence, access time, usage, and completed result in SQLite
- [ ] 4.5 Show company research without changing score or band
- [ ] 4.6 Show the requested limited-online-presence flag with the searches performed and their limits
- [ ] 4.7 Test sources, uncertainty, prompt injection, timeout, retry, duplicate requests, and cost limits

## 5. Slice 3 - Synchronous Education and Certification Research

- [ ] 5.1 Let the recruiter start education and certification research for a stored analysis
- [ ] 5.2 Add an idempotent education-research endpoint with a bounded timeout
- [ ] 5.3 Define the Web Search prompt and schema for institutions, programs, degrees, certificates, dates, accreditation, city, and country
- [ ] 5.4 Store cited results in SQLite and highlight unexplained location differences for review
- [ ] 5.5 Show education research separately from company and LinkedIn results
- [ ] 5.6 Test evidence, uncertainty, timeout, retry, duplicate requests, and cost limits

## 6. Slice 4 - Synchronous LinkedIn Discovery and Comparison

- [ ] 6.1 Let the recruiter start candidate-scoped LinkedIn discovery for a stored analysis
- [ ] 6.2 Add an idempotent LinkedIn-discovery endpoint with a bounded timeout
- [ ] 6.3 Return possible profiles with match evidence and confidence without claiming identity
- [ ] 6.4 Report visible photo and connection-count availability and apply the agreed completeness threshold without analyzing appearance
- [ ] 6.5 Show a `linkedin_not_found` flag with the searches performed and their limitations
- [ ] 6.6 Require recruiter confirmation before profile-to-CV comparison
- [ ] 6.7 Compare a confirmed profile's companies, roles, dates, location, and education with the CV
- [ ] 6.8 Test wrong-person matches, ambiguity, no profile, evidence, timeout, retry, and candidate isolation

## 7. Slice 5 - V1 Hardening in the Existing Architecture

- [ ] 7.1 Add versioned SQLite cache entries for reusable company, institution, program, and certificate research
- [ ] 7.2 Reuse cache entries without leaking candidate data and record cache use in the audit
- [ ] 7.3 Measure single-CV and realistic-batch latency, request failures, token use, and cost
- [ ] 7.4 Set request timeout, batch size, retry, search, and cost limits from measurements
- [ ] 7.5 Verify original-file deletion, national-ID redaction, development retention, and the approved production retention
- [ ] 7.6 Add request metrics, structured logs, research error reporting, cache metrics, and an operations guide
- [ ] 7.7 Run the wider permitted corpus regression and agree on acceptance criteria with HR
- [ ] 7.8 Get stakeholder acceptance, enable the feature, and keep a tested deterministic-only rollback
- [ ] 7.9 Create a separate architecture proposal only if measured volume or failures require background processing
