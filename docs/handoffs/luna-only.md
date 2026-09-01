# Luna-only implementation handoff

## Goal

Implement the comparison variant on `experiment/luna-only-analysis`. It must
start from the exact shared-cleanup commit recorded in
`docs/cv-analyzer-architecture-reset-handoff.md`.

This variant uses one GPT-5.6 Luna request to interpret the complete original
CV. It does not use Docling and does not recreate deterministic semantic CV
parsing.

Planned isolated worktree:

`/home/sacewicz/Projects/Work/lightningtalk-cv-analyzer-luna-only`

Local isolation: Compose project `cv-analyzer-luna-only`, web port `3022`, API
database `/app/data/luna_only.db`, and auth database
`/app/data/luna_only_auth.db` in this worktree's ignored `.env.local`.

## Input path

Use the Responses API `input_file` input with the original PDF or DOCX. The
official API supports both formats. PDF input supplies extracted text and page
images to an image-capable model. Non-PDF documents such as DOCX supply
extracted text.

Official references:

- https://developers.openai.com/api/docs/guides/file-inputs
- https://developers.openai.com/api/docs/models/gpt-5.6-luna

The product does not need scan-only CV support. Add a small local embedded-text
sufficiency gate before the API request. It may inspect PDF text layers and
DOCX text content, but it must not infer sections, employment, education,
dates, or relationships. Reject scan-only or image-only input clearly before
calling Luna.

Do not use Docling in this branch.

## Model pass

Run one Luna request that returns the shared `base-analysis-v2` semantic
contract:

- profile;
- employment;
- education;
- review findings;
- source-supported missing candidates;
- ambiguity and coverage gaps.

Initial configuration:

- model: pinned `gpt-5.6-luna`;
- Responses API;
- `reasoning.effort = low`;
- `store = false`;
- no tools;
- strict Structured Output;
- explicit timeout and bounded transport failure handling;
- no automatic semantic retry.

The single pass may add information it finds while checking completeness, but
every semantic value must cite exact evidence. It must return unknown or
ambiguous when it cannot support a value. Code validates schema, literal
evidence, bounds, and record relations before assembling the report.

## Provenance in this variant

The model does not receive Docling block IDs. Use the shared evidence shape
with strategy-specific references:

- exact literal excerpt;
- page number for PDF when available;
- stable local text-segment ID produced only by the sufficiency/evidence
  extractor;
- offsets into that local segment when available.

The local extractor exists only to validate literal evidence and reject empty
documents. It must not become a second document-understanding system.

## Shared behavior

Reuse the common implementation for:

- phone, e-mail, literal URL, postal candidates, GeoNames, and EU information;
- persistence and ownership;
- upload and batch limits;
- UI and document preview;
- automatic company, education, and LinkedIn research;
- cache provenance and usage accounting;
- retention and deletion.

The report must expose strategy name `luna-only` and a pinned strategy version.

## Acceptance

- PDF and DOCX `input_file` requests use the original upload.
- Scan-only input is rejected locally before an OpenAI request.
- One request returns profile, employment, education, and review data in the
  shared schema.
- Missing source-supported profile, employment, or education data can be added
  by the completeness part of the same pass.
- Unsupported additions fail validation.
- A technology such as `MongoDB` is not accepted as an employer without
  employment evidence.
- Correct individual strings cannot be grouped into one record without
  relation evidence.
- One bad record does not erase unrelated valid records.
- Research uses only accepted output.
- The UI and persisted report contain no DU, Structural Audit, ESCO, redaction,
  score, band, file metadata, or live link checker.
- The same evaluation corpus and measurements used by the Docling variant are
  recorded for comparison.

Do not make live OpenAI calls unless that session has explicit cost
authorization. Fake-client tests and anonymous fixtures come first.
