# Architecture

CV Analyzer runs the `document-analysis` strategy and validates
its output against the `base-analysis-v2` contract.

```text
PDF or DOCX upload
    -> Docling native-text conversion with OCR disabled
    -> minimal SourceDocument evidence projection
    -> concurrent profile, employment, and education model passes
    -> field, literal-evidence, and record-relation validation
    -> sequential model reviewer using validated ID-based operations
    -> shared mechanical enrichment
    -> base-analysis-v2 validation and SQLite persistence
    -> recruiter UI and optional public research
```

## Boundaries

- Semantic profile, employment, and education values require literal source
  evidence. Fields in one record require evidence that they belong together.
- The reviewer may add a missed candidate only through the same evidence and
  relation validation used for extractor output.
- Deterministic code is limited to mechanical facts and comparisons: phones,
  e-mails, literal URLs, postal candidates, e-mail-provider typos, GeoNames
  resolution, accepted postal-address checks, and informational EU status.
- A postal-looking token is not a candidate address until supported context
  accepts that relation.
- Education research distinguishes supported institution existence, cited conflicts,
  and insufficient evidence. Only a sourced institution conflict creates a "What to check"
  finding; missing research evidence remains a panel status. Older results without
  this assessment remain readable and need fresh research for a new verdict.
- Company research lowers overstated aggregate confidence and drops empty or
  contradictory optional operating periods without losing other sourced findings.
  Subject, schema and evidence validation remain required.
- Company lifecycle events carry exact public source URLs. Owner-scoped code
  compares high-confidence, unambiguous business bounds with accepted employment
  start dates using date intervals. Unclear continuity, missing evidence and
  ambiguous entities produce no flag. These comparisons are never cached publicly.
- Company, education, and LinkedIn research receives only accepted subjects.
  Research is optional, cited, read-only decision support and cannot mutate the
  base analysis.
- The overview EU row classifies only the declared location. A phone prefix alone
  leaves location unknown; a phone/location country difference is listed under "What to check"
  as a consistency signal, not a judgment.
- The system does not perform identity, honesty, residence, nationality, work
  eligibility, or automatic hiring verification.

## Removed architecture

The deterministic Document Understanding pipeline, Structural Audit, ESCO,
national-ID redaction, score/band/weights, file metadata, live-link inspection,
and the monolithic document-AI retry path are intentionally absent. Old pilot
reports are not a compatibility surface. Do not recreate these systems as
fallbacks or derive research subjects from their former contracts.

## Runtime and privacy

Only text-bearing PDF and DOCX files are supported. Scan-only or image-only
documents fail explicitly; OCR is not attempted. OpenAI response storage is
disabled. Upload bytes are processed in memory during analysis; after a report
commits, the original PDF/DOCX is retained only for the analysis-retention
window. Raw CV text, evidence, model output, and secrets must not enter logs.

The API persists validated reports and owner-scoped lifecycle data in SQLite.
AI accounting is separate from mutable report/research rows: `ai_usage_events`
is an append-only, non-PII ledger of provider/model, operation, token counts,
pricing/FX snapshots, estimated cost, cache status, and a pseudonymous analysis
identifier. Profile Builder records each extraction, summary, AI action, and translation provider attempt in the same ledger using independent random accounting identifiers, before downstream validation can discard billed responses. Global totals include these operations; report averages exclude Profile Builder. Historical unrecorded usage cannot be reconstructed. `processed_report_events` records each completed or partial base report once.
Normal report deletion and retention remove the report association data but
intentionally retain those pseudonymous accounting facts so deployment lifetime
totals remain monotonic; retained accounting rows cannot reconstruct CV text,
evidence, prompts, model responses, candidate details, or e-mail addresses.

After a report is persisted, the original uploaded PDF or DOCX is stored
alongside it so the recruiter can preview it again; the copy is served only to
the authenticated owning user and is deleted with the analysis or by retention purge.
GeoNames locality and postal indexes are prepared by a one-shot Compose service
and mounted read-only by the API. Operational setup, recovery, retention,
feedback rollout, and backups are documented in `docs/operations.md` and
`docs/reference-data/geonames.md`.

The authoritative executable contracts are:

- `apps/api/src/cv_validator/analysis/strategy.py`;
- `apps/api/src/cv_validator/analysis/contracts/base-analysis.schema.json`;
- `apps/api/src/cv_validator/analysis/validation.py`;
- `apps/api/src/cv_validator/analysis/document_analysis.py`.


## Profile Builder

The CVtoBlind-replacement workflow is restored from `origin/feature/profile-builder`
(`5f4b934`) without merging its obsolete analyzer implementation. The builder does not alter the analyzer's prompts or reviewer policy. Analyzer
ownership and research hardening remain separate concerns. Profile conversion is a separate editable-document workflow:

`PDF/DOCX -> current text-only Docling converter -> bounded structured extraction -> CandidateProfile -> editing + visibility/template snapshot -> native DOCX -> LibreOffice PDF`.

- `profile_builder.py` owns the canonical profile, templates, preferences, output
  visibility projection, and DOCX/PDF renderers.
- `profile_builder_ai.py` owns only profile extraction, Summary, AI Actions and
  Translation. The existing fast bounded requests, selected-section proposals,
  stable cache prefix, and `store=false` are preserved.
- `profile_builder_privacy.py` retains the builder's supported national-ID masking
  invariant. It does not introduce a masking pass into CV Analyzer.
- `api/profile_builder_routes.py` and `api/profile_builder_store.py` own the
  separate API and owner-scoped profile tables in the existing database. Existing
  profile/template/preferences rows from the old branch remain readable.
- The authenticated Next.js catch-all proxy derives the owner capability server
  side, bounds multipart/JSON bytes before parsing, and marks responses private
  and non-cacheable. Keep the FastAPI service private behind this proxy.
- Saved profiles include the exact template and visibility snapshot. Private
  templates remain owner scoped; explicitly shared templates and custom-field
  definitions retain the existing internal-organization scope.

Profile Builder availability is independent of the per-browser switch for optional
public-company/education/LinkedIn research. Missing PDF conversion does not make
CV Analyzer unready; saved-profile editing and DOCX export still work.
