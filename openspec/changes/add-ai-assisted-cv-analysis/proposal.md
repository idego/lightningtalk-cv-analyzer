## Why

The current analyzer checks location consistency with fixed rules. It cannot detect many semantic conflicts or suspicious patterns, so recruiters must find them by hand. We need an AI-assisted document review that returns quickly, plus optional web research when the recruiter asks for it.

## What Changes

- Preserve source text and page numbers during ingestion. Format this text as simple Markdown for AI analysis.
- Add an OpenAI Document Analyzer. It extracts facts, findings, uncertainty, evidence, and research candidates from one CV without web access.
- Keep score and band calculation deterministic. AI findings support human review but never reject or advance a candidate.
- Return the base report before any web research starts.
- Let the recruiter start company, education/certification, and LinkedIn research separately.
- Run research in the background with OpenAI Web Search. Add cited results to the existing report.
- Add durable priority jobs, scalable workers, exclusive job claims, retries, safe result writes, and a shared cache for public entities.
- Let the frontend poll job state and show results as they arrive.
- Use the private, gitignored corpus only to create anonymous prompt rules and eval cases. The running application does not use this corpus.

## Capabilities

### New Capabilities

- `ai-document-analysis`: Analyze one CV with OpenAI. Return structured findings, evidence, uncertainty, and research candidates.
- `ai-assisted-research`: Run optional company, education/certification, and LinkedIn web research. Return cited results and require human confirmation for identity matches.
- `analysis-job-processing`: Store and process priority jobs across scalable workers. Track ownership, retries, status, and cache use.

### Modified Capabilities

- `cv-ingestion`: Preserve page numbers and source text for simple Markdown. Keep the current error for files without usable text.
- `consistency-scoring`: Add AI findings to the report but keep score and band deterministic.
- `location-analysis-api`: Add persistent analysis state, job status, report polling, and optional research requests.
- `frontend-analysis-workflow`: Show the base report first. Let the user start research and see new results and errors.
- `compose-orchestration`: Add queue and worker services. Keep the web service as the only public entrypoint.

## Impact

- Backend: ingestion, OpenAI calls, prompts, schemas, report types, storage, jobs, workers, research cache, API routes, and tests.
- Frontend: upload state, report polling, research controls, progressive findings, and job status.
- Runtime: OpenAI credentials, Web Search, a durable queue, workers, configurable concurrency, and a later production database choice.
- Privacy: send candidate data only to the approved OpenAI account. Delete original CV files after processing. Keep national-ID values redacted and all reports framed as decision support.
- Evaluation: derive a versioned prompt and eval process from anonymous lessons in the private corpus.
