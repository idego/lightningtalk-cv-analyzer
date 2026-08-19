## Context

The FastAPI pipeline now runs in one request. It reads a PDF or DOCX, extracts location signals, calculates a rules-based score and band, stores the report in SQLite, and returns it through Next.js. It has no LLM, web research, queue, worker, or progressive report state.

The rules in `AGENTS.md` still apply. The product supports human review. It does not verify identity or location and does not make hiring decisions. The score and four bands remain deterministic. The system redacts national-ID values. The approved OpenAI account can process candidate data. The private `data/` corpus stays gitignored and is never a runtime input.

See `proposal.md` for scope and `docs/proposed-ai-architecture.md` for the short stakeholder summary.

## Goals / Non-Goals

**Goals:**

- Return a useful AI-assisted base report before optional research starts.
- Give each candidate and job a fresh model context.
- Process large batches with durable priority jobs and scalable workers.
- Let recruiters choose which research jobs use time and money.
- Keep evidence, audit data, retries, and deterministic scoring clear and testable.
- Ship one useful result in each vertical slice.

**Non-Goals:**

- Support Anthropic or add a provider abstraction in the first version.
- Add OCR for image-only CVs.
- Use browser automation, authenticated LinkedIn access, or private data scraping.
- Verify identity or automate a hiring decision.
- Choose the final broker, database, cache lifetime, or worker library before the job-processing slice.
- Add Tinder-style CV review or other batch-review experiments.

## Decisions

### D1: Build vertical slices

Start with prompt and eval work. Then ship one-CV document analysis, durable jobs, three research categories, and production hardening. Each slice must produce a result that users or operators can test.

Do not build all queue and research infrastructure first. That would delay the main proof: AI document analysis must help recruiters.

### D2: Keep `pdfplumber` and use simple Markdown

Keep faithful text and page numbers in addition to the current normalized lines. The formatter adds page separators. It does not guess headings, tables, columns, or relationships.

We rejected PDF Inspector as the default. In the corpus test, it made cleaner Markdown but damaged more text, links, and column relationships. Direct PDF input can remain a future eval, but it is not the baseline.

### D3: Make one bounded OpenAI call per CV

Use the OpenAI Responses API and GPT-5.6 Luna. Start with medium reasoning and strict structured output. Send one CV and versioned instructions. Do not enable web tools. Return facts, findings, evidence, uncertainty, and research candidates.

Do not add a provider abstraction or a document agent. One document with a fixed output is a bounded workflow.

### D4: Keep AI outside the verdict

Only fixed rules can change the score and band. AI findings have separate `importance` and `confidence` values. The UI can highlight an important finding, but the finding cannot change weights or bands.

This keeps the verdict repeatable while AI helps the reviewer.

### D5: Return the base report before research

Document analysis and fixed rules create the first useful report. Research does not start by default. The recruiter can start company, education/certification, or LinkedIn work separately.

Running every research job for every CV would waste time and money.

### D6: Schedule research with code

`ResearchJobScheduler` is normal application code. It checks the user's choices, validates research candidates, checks cache, removes duplicate requests, creates no more than one job per category and CV, and reports category status.

The job types are:

- `company_research`
- `education_research`
- `linkedin_discovery`

One category job can handle several entities from the same CV, within fixed search and cost limits. We do not need an AI coordinator for these fixed choices.

### D7: Use hosted Web Search in read-only mode

Research jobs use OpenAI Web Search and keep its source data. They do not use browser automation or logged-in sessions. Treat all page content as untrusted data. A page cannot change the job's instructions, tools, or scope.

LinkedIn discovery returns possible profiles. The recruiter must confirm a profile before the system compares it with the CV.

### D8: Store jobs and scale workers with Docker

The API stores the analysis and jobs before it returns. A worker service claims jobs from a durable queue. Deployment settings control worker capacity. Start with a global limit of three.

Document jobs have higher priority than research jobs. Each worker rebuilds the model request from stored input and versioned settings. It never reuses `previous_response_id` or another candidate's model context.

Use at-least-once delivery. A lease gives one worker temporary ownership. A heartbeat keeps the lease active. An expired lease allows a retry. Idempotency keys and unique result records prevent duplicate findings.

Do not use FastAPI `BackgroundTasks`. A restart can lose those tasks, and they do not scale as separate Docker workers.

### D9: Poll job state in the first frontend version

Return a stable ID for each file. The frontend polls non-terminal jobs, shows each base report as soon as it is ready, and adds research results later.

Do not add WebSockets or SSE yet. These jobs update rarely, and polling has a simpler failure model.

### D10: Cache public-entity research

Cache company, institution, program, and certification results by normalized entity, research version, and freshness window. Keep source and retrieval data on cache hits. Keep LinkedIn and candidate-profile comparisons scoped to one candidate.

### D11: Build prompts and evals from private corpus lessons

Use the private corpus during development to create an anonymous finding taxonomy, forbidden-signal rules, prompt, schema, and eval set. Never copy raw CVs or HR comments into tracked files or runtime images.

Start with four CVs. Measure expected-finding recall, unsupported findings, evidence accuracy, time, and cost. Use the full permitted corpus only when broader regression testing is useful.

## Risks / Trade-offs

- [AI misses findings] -> Use corpus-based evals, a completeness checklist, explicit unknowns, and versioned prompts.
- [AI invents a finding] -> Require a CV excerpt or web source and validate every structured result.
- [Research matches the wrong person] -> Show uncertainty and require recruiter confirmation for LinkedIn.
- [Research costs grow] -> Make it optional, limit searches and concurrency, remove duplicates, and cache public entities.
- [Research delays base reports] -> Give document jobs higher priority.
- [A worker fails] -> Use leases, retries, idempotency keys, and unique result writes.
- [SQLite blocks concurrent work] -> Choose and load-test the broker and production database in the job-processing slice.
- [A web page injects instructions] -> Give research read-only tools and treat page text only as data.
- [Private corpus enters Git] -> Keep `data/` ignored and commit only anonymous rules and tests.
- [AI output varies] -> Keep score and band deterministic and store the model, prompt, schema, and evidence used for each result.

## Migration Plan

1. Add page-aware ingestion and AI types behind a disabled feature flag.
2. Build the prompt, schema, four-CV eval, and OpenAI call.
3. Test the AI base report with internal reviewers. Keep deterministic scoring unchanged.
4. Add stored jobs, workers, queue infrastructure, and polling routes.
5. Move the frontend to stable analysis IDs and progressive results.
6. Add company, education, and LinkedIn research in separate slices.
7. Add cache, load tests, limits, retention checks, and monitoring.
8. Enable the feature after stakeholder and eval approval.

Keep the current deterministic endpoints behind the feature flag until the new flow is accepted. Disabling AI and research must not remove stored deterministic reports.

## Open Questions

- Which broker, job library, and production database should the job-processing slice use?
- Which concurrency, lease, timeout, retry, and backoff defaults pass the load test?
- How long should public-entity cache entries remain valid?
- Which GPT-5.6 Luna snapshot and reasoning level pass the four-CV eval?
- Which per-CV and per-batch cost limits should production enforce?
- Which retention period should replace the 90-day development value?
