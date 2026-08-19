## Context

The application already has a clear top-level architecture: Next.js authenticates the user and proxies uploads to FastAPI; FastAPI calls a library-first Python pipeline; the pipeline parses PDF or DOCX, applies deterministic rules, builds a report, and stores audit data in SQLite. Docker Compose runs `web` and `api`.

The V1 extends this flow instead of replacing it. AI document analysis runs inside the existing analysis request. Optional company, education, and LinkedIn checks run through separate synchronous requests to the same API. We accept the latency and sequential batch behavior for the first version, then measure them.

The rules in `AGENTS.md` still apply. The product supports human review. It does not verify identity or location and does not make hiring decisions. The score and four bands remain deterministic. The system redacts national-ID values. The approved OpenAI account can process candidate data. The private `data/` corpus stays gitignored and is never a runtime input.

## Goals / Non-Goals

**Goals:**

- Add every business check from Magdalena's HR backlog.
- Return a useful AI-assisted report from the existing API flow.
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

## Decisions

### D1: Extend the current pipeline

Keep the current path:

```text
Next.js -> FastAPI -> ingestion -> rules + OpenAI -> report -> SQLite
```

The OpenAI call is another application service used by `pipeline.py`. It is not a new deployable service. Report and persistence types grow to hold structured facts, AI findings, research candidates, and completed research results.

### D2: Keep `pdfplumber` and use simple Markdown

Keep faithful text and page numbers in addition to the current normalized lines. The formatter adds page separators. It does not guess headings, tables, columns, or relationships.

We rejected PDF Inspector as the default. In the corpus test, it made cleaner Markdown but damaged more text, links, and column relationships. Direct PDF input can remain a future eval, but it is not the baseline.

### D3: Make one bounded OpenAI call per CV

Use the OpenAI Responses API and GPT-5.6 Luna. Start with medium reasoning and strict structured output. Send one CV and versioned instructions. Do not enable web tools. Return structured facts, findings, evidence, uncertainty, and research candidates.

Each call starts without a previous response or another candidate's context. The current batch endpoint can call this flow sequentially. V1 documents and enforces a practical batch limit based on measured request duration.

### D4: Keep AI outside the verdict

Only fixed rules can change the score and band. AI findings have separate `importance` and `confidence` values. The UI can highlight an important finding, but the finding cannot change weights or bands.

Requested weak signals remain visible. For example, the report can flag that no LinkedIn profile was found, a profile has no visible photo or sufficient public connection count, or a company has little detectable online presence. It must also show the evidence and search limits.

### D5: Run optional research through normal API requests

Document analysis and fixed rules create the base report. Research does not start by default. The recruiter can start company, education/certification, or LinkedIn research separately.

Each button calls a dedicated FastAPI endpoint. The request validates stored research candidates, checks SQLite cache where allowed, calls OpenAI Web Search, validates the structured result, stores it, and returns the updated category. The frontend shows a loading state until that request succeeds or fails.

There is no background job state in V1. If a request fails or the page closes, the user can retry it. Completed writes are idempotent per analysis, category, and research version.

### D6: Use hosted Web Search in read-only mode

Research uses OpenAI Web Search and keeps its source data. It does not use browser automation or logged-in sessions. Treat all page content as untrusted data. A page cannot change the request's instructions, tools, or scope.

LinkedIn discovery returns possible profiles. The recruiter must confirm a possible profile before a later comparison treats its differences from the CV as relevant.

### D7: Keep the existing runtime and persistence

Docker Compose continues to run `web` and `api`. Only `web` publishes a host port. The API stores reports, research results, prompt versions, usage, and audit records in SQLite.

Cache company, institution, program, and certification results in SQLite by normalized entity, research version, and freshness window. Keep source and retrieval data on cache hits. Keep LinkedIn results scoped to one candidate.

### D8: Treat the HR backlog as required product scope

The system must extract contact, education, and employment data; produce the requested phone and location signals; check companies, education, and LinkedIn; and return a complete per-candidate checklist in JSON and HTML.

The report names each observed signal precisely. It does not turn a missing profile, foreign location, low public footprint, name, photo, or other proxy into proof of fraud, nationality, identity, or physical location.

### D9: Build prompts and evals from private corpus lessons

Use the private corpus during development to create an anonymous finding taxonomy, completeness checklist, prompt, schema, and eval set. Never copy raw CVs or HR comments into tracked files or runtime images.

Start with four CVs. Measure expected-finding recall, unsupported findings, evidence accuracy, latency, tokens, and cost. Use the full permitted corpus only for broader regression testing.

## Risks / Trade-offs

- [Requests take longer] -> Show clear loading states, set explicit timeouts, measure latency, and set a practical V1 batch limit.
- [A request fails after work starts] -> Store results only after validation and make the user-triggered research action safe to retry.
- [The API process restarts] -> Accept loss of in-flight work in V1; completed reports remain in SQLite.
- [AI misses findings] -> Use corpus-based evals, a completeness checklist, explicit unknowns, and versioned prompts.
- [AI invents a finding] -> Require a CV excerpt or web source and validate every structured result.
- [Research matches the wrong person] -> Show uncertainty and require recruiter confirmation for LinkedIn comparison.
- [Research costs grow] -> Make it optional, limit searches, remove duplicate requests, and cache reusable public entities in SQLite.
- [A web page injects instructions] -> Give research read-only tools and treat page text only as data.
- [Private corpus enters Git] -> Keep `data/` ignored and commit only anonymous rules and tests.
- [A requested weak signal is overinterpreted] -> Keep the signal visible, name the observed fact precisely, show its limits, and leave the conclusion to the recruiter.
- [V1 cannot handle required volume] -> Record batch duration and failure data, then propose only the smallest approved infrastructure change supported by measurements.

## Migration Plan

1. Keep the current endpoints and deterministic behavior as the default.
2. Add page-aware ingestion and AI types behind a disabled feature flag.
3. Build the prompt, schema, four-CV eval, and synchronous OpenAI call.
4. Add structured facts and AI findings to the existing report and SQLite audit.
5. Update the frontend to show the completed AI-assisted report.
6. Add company, education, and LinkedIn research as separate synchronous actions.
7. Add SQLite cache, request limits, retention checks, metrics, and an operations guide.
8. Measure realistic batches and get stakeholder acceptance before enabling the feature.

Disabling AI and research must preserve the current deterministic flow. A queue, workers, or database migration require a separate change proposal and stakeholder approval.

## Open Questions

- Which GPT-5.6 Luna snapshot and reasoning level pass the four-CV eval?
- What timeout and maximum batch size keep the synchronous V1 usable?
- Which per-CV and per-batch cost limits should production enforce?
- How long should SQLite research cache entries remain valid?
- Which retention period should replace the 90-day development value?
- What configured threshold should the LinkedIn profile-completeness signal use?
- Which reference data and rule should define a small or atypical non-EU locality?
