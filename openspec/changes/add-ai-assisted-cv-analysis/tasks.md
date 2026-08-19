## 1. Slice 0 - Prompt and Eval Baseline

- [ ] 1.1 Get project-owner approval for the proposal, design, and roadmap
- [ ] 1.2 Derive an anonymous finding taxonomy, forbidden-signal rules, and completeness checklist from the private `data/` corpus
- [ ] 1.3 Select four CVs for the first eval and record expected findings, accepted unknowns, and unsupported-output checks outside Git
- [ ] 1.4 Define versioned Document Analyzer instructions and a strict schema for facts, findings, evidence, uncertainty, and research candidates
- [ ] 1.5 Add a local eval command that records recall, unsupported findings, evidence accuracy, time, tokens, and estimated cost
- [ ] 1.6 Test GPT-5.6 Luna with medium reasoning and record the accepted baseline

## 2. Slice 1 - Page-Aware Input

- [ ] 2.1 Keep per-page source text and page IDs while preserving current normalized lines and contact/body regions
- [ ] 2.2 Generate simple page-separated Markdown without guessed headings, tables, columns, or relationships
- [ ] 2.3 Detect insufficient text and return a clear error for scan-only inputs
- [ ] 2.4 Test PDF and DOCX page boundaries, current normalization, and insufficient-text errors

## 3. Slice 1 - Useful AI Base Report

- [ ] 3.1 Add OpenAI settings, secret documentation, a feature flag, and a pinned GPT-5.6 Luna configuration
- [ ] 3.2 Call the OpenAI Document Analyzer without web tools and validate its schema
- [ ] 3.3 Reject invalid evidence, unsupported demographic signals, and malformed research candidates
- [ ] 3.4 Store AI findings, importance, confidence, evidence, versions, usage, and audit data
- [ ] 3.5 Add AI findings to the report without changing deterministic score, band, or rule findings
- [ ] 3.6 Show `Wymaga uwagi`, `Warto wiedzieć`, and collapsed `Pozostałe sygnały` in the UI
- [ ] 3.7 Test the full single-CV flow in the backend, frontend, and four-CV eval

## 4. Slice 2 - Durable Jobs and Progressive Results

- [ ] 4.1 Choose and document the queue, worker library, production database direction, and local setup
- [ ] 4.2 Store analyses and jobs with priority, status, attempts, idempotency key, lease, and timestamps
- [ ] 4.3 Add atomic claims, heartbeats, expired-lease recovery, bounded retries, and safe completion
- [ ] 4.4 Add a worker that rebuilds each request from stored input and versioned settings
- [ ] 4.5 Add configurable worker capacity and Compose services for the queue and workers
- [ ] 4.6 Add async single/batch submission, stable file IDs, report polling, and isolated errors
- [ ] 4.7 Poll each file in the frontend and show its base report when ready
- [ ] 4.8 Test concurrency, worker failure, duplicate completion, mixed batches, and priority

## 5. Slice 3 - Company Research

- [ ] 5.1 Let the recruiter start company research after the base report is ready
- [ ] 5.2 Schedule no more than one deduplicated `company_research` job per CV
- [ ] 5.3 Define the Web Search prompt and schema for company existence, dates, work, location, and employer/client/project relations
- [ ] 5.4 Store cited findings, confidence, access time, and neutral insufficient-evidence results
- [ ] 5.5 Show company research status and results without changing score or band
- [ ] 5.6 Test sources, uncertainty, prompt injection, isolated failure, and cost limits

## 6. Slice 4 - Education and Certification Research

- [ ] 6.1 Let the recruiter start one deduplicated education/certification job per CV
- [ ] 6.2 Define the Web Search prompt and schema for institutions, programs, degrees, certificates, dates, and accreditation
- [ ] 6.3 Store cited results and keep foreign education and missing public data neutral
- [ ] 6.4 Show education status and results apart from company and LinkedIn work
- [ ] 6.5 Test evidence, uncertainty, isolated failure, and cost limits

## 7. Slice 5 - LinkedIn Discovery and Comparison

- [ ] 7.1 Let the recruiter start a candidate-scoped LinkedIn discovery job
- [ ] 7.2 Return possible profiles with match evidence and confidence without claiming identity
- [ ] 7.3 Require recruiter confirmation before profile-to-CV comparison
- [ ] 7.4 Compare the confirmed profile's companies, roles, dates, location, and education with the CV
- [ ] 7.5 Show possible matches, confirmation state, progress, results, and neutral no-match results
- [ ] 7.6 Test wrong-person matches, ambiguity, no profile, evidence, and candidate isolation

## 8. Slice 6 - Cache, Scale, and Production Readiness

- [ ] 8.1 Define entity keys, cache versions, freshness rules, and invalidation for reusable public research
- [ ] 8.2 Reuse cache entries without leaking candidate data and record cache use in the audit
- [ ] 8.3 Load-test large batches and record throughput, queue delay, API delay, rate limits, and cost
- [ ] 8.4 Set concurrency, timeout, retry, backoff, search, and cost limits from test results
- [ ] 8.5 Verify CV deletion, national-ID redaction, development retention, and the approved production retention
- [ ] 8.6 Add metrics, structured logs, failed-job views, cache metrics, and an operations guide
- [ ] 8.7 Run the wider permitted corpus regression and agree on acceptance criteria with HR
- [ ] 8.8 Get stakeholder acceptance, enable the feature, and keep a tested deterministic-only rollback
