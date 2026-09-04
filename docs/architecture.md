# Architecture

CV Analyzer runs one `document-analysis` strategy and validates
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
- Company, education, and LinkedIn research receives only accepted subjects.
  Research is optional, cited, read-only decision support and cannot mutate the
  base analysis.
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
identifier. `processed_report_events` records each completed or partial base report once.
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
