## Why

The current analyzer checks location consistency with prototype fixed rules. Several rules are useful foundations, but others guess from weak proxies such as spelling, currency, date formatting, or the first place name in a section. They should not be preserved merely for compatibility. We need to add AI-assisted review and optional public-web checks while keeping the repository's service architecture and replacing inaccurate internals.

## What Changes

- Replace the flattened `ParsedCV` internals with page-aware source text, stable page IDs, and exact source mapping. Format the source as simple page-separated Markdown for AI analysis.
- Replace prototype location heuristics with a small deterministic core that separates source-mapped `Candidate`, `Fact`, `Observation`, and `ScoringSignal` values behind one `DeterministicAnalysisResult`. Ambiguous values remain unknown.
- Resolve locations through a replaceable `LocationResolver` backed in V1 by a versioned offline GeoNames index built from `cities500`, `countryInfo`, and filtered `alternateNamesV2` records. The application never downloads reference data while analyzing a CV.
- Send the complete page-aware CV plus versioned deterministic observations to one synchronous OpenAI Document Analyzer call in the existing FastAPI pipeline.
- Return structured contact, education, and employment data plus cited AI findings in the current report.
- Let the model cite stable source-line IDs and let code materialize exact page excerpts, so the model never has to reproduce candidate text byte-for-byte.
- Surface possible typos of well-known public email-provider domains as code-owned, non-scoring `worth knowing` observations with an explicit confirmation caveat.
- Make Magdalena's HR backlog the required business scope: location flags, company checks, education checks, LinkedIn checks, a complete flag checklist, and JSON/HTML results.
- Keep score and band calculation deterministic. Only code-owned facts may affect them. AI-derived facts and findings support human review but never enter the verdict path, reject, or advance a candidate.
- Preserve the current JSON fields and add one nested `deterministic` object containing facts, observations, authority, evidence, and deterministic versions.
- Let the recruiter start company, education/certification, and LinkedIn research separately. Each action runs as a normal synchronous request through the existing API.
- Use OpenAI Web Search for research and store completed results in the existing SQLite persistence layer.
- Keep the current Next.js, FastAPI, SQLite, and Docker Compose service boundaries and synchronous external API shape. Internal parsing, extraction, and report models may be replaced when the current prototype behavior is inaccurate.
- Use the private, gitignored corpus only to create anonymous prompt rules and eval cases. The running application does not use this corpus.

This V1 does not add a broker, background queue, worker service, leases, polling, or a new database. It also does not preserve weak prototype signals as scored evidence, score postal compatibility before calibration, or change weights and band thresholds without separate calibration and project-owner approval. Infrastructure changes require separate approval and evidence from measured V1 usage.

## Capabilities

### New Capabilities

- `ai-document-analysis`: Analyze one CV with OpenAI inside the existing request. Return structured facts, findings, evidence, uncertainty, and research candidates.
- `ai-assisted-research`: Run recruiter-selected company, education/certification, and LinkedIn web research through synchronous API actions. Return cited results and require human confirmation for identity matches.

### Modified Capabilities

- `cv-ingestion`: Preserve page numbers and source text for simple Markdown. Keep the current error for files without usable text.
- `location-signal-extraction`: Replace prototype proxy signals with versioned, code-owned candidates, facts, observations, and scoring signals for claimed location, phone country, locality resolution, and other mechanically defensible observations.
- `consistency-scoring`: Add requested location and AI findings to the report while keeping score and band based only on code-owned facts.
- `location-analysis-api`: Return AI-assisted reports and expose synchronous research actions through the existing FastAPI service.
- `frontend-analysis-workflow`: Show the completed base report, run selected research with loading states, and update the report after each request.

## Impact

- Backend: page-aware ingestion, deterministic candidate extraction and validation, a versioned offline GeoNames index, raw/redacted document boundaries, OpenAI calls, prompts, schemas, report types, SQLite persistence, research services, API routes, and tests. Prototype extractors may be removed or replaced.
- Frontend: base-report findings, structured facts, research controls, loading and error states, and updated results.
- Runtime: OpenAI credentials and request-level timeouts within the existing `web` and `api` services.
- Privacy: send candidate data only to the approved OpenAI account. Delete original CV files after processing. Replace national-ID values with same-length masks before Markdown, AI, persistence, logs, or reports, and persist only a hash of redacted canonical text.
- Reference data: build GeoNames snapshots through a manually run, approved quarterly process with a manifest containing source URLs, snapshot date, SHA-256 values, index schema version, filtering rules, and record counts.
- Evaluation: derive a versioned prompt and eval process from anonymous lessons in the private corpus.
- Product scope: keep every HR-requested signal visible for review, including weak or missing-evidence signals, while stating its evidence and limitations.
