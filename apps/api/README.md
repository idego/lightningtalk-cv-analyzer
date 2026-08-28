## CV Validator API

Backend service for CV location-consistency analysis.

Run tests from this directory:

```bash
PYTHONPATH=src pytest
```

Reports optionally include `file_details` and `link_inspection`. File details
are a bounded allowlist of PDF/DOCX metadata for neutral reviewer context.
Link inspection inventories visible HTTP(S) URLs and embedded hyperlink targets,
then records deterministic `REACHABLE`, `SUSPICIOUS`, `UNAVAILABLE`, or
`NOT_CHECKED` outcomes. Suspicious outcomes are document-review prompts, not
proof of lying, fraud, identity, or physical location; unavailable outcomes
are inconclusive and remain neutral. Link checks use no AI or paid service and
never persist response bodies, cookies, request headers, credentials, or URL
query/fragment material.

The legacy numeric score and band remain in the API for compatibility. The
recruiter UI does not present them as an overall CV or candidate assessment.

Document understanding runs after mandatory national-ID redaction and before
optional AI enrichment. Its public DTO is closed and bounded; persistence, reload,
retry replacement, and API serialization all use the same sanitizer. AI receives
a same-length masked visible-source projection and bounded code-owned context, and
cannot overwrite deterministic/code-owned fields or influence score/band output.

Reference-data operations are build-time only. See the repository README for the
pinned ESCO index rebuild command. Do not add runtime taxonomy downloads or send CV
content to a taxonomy provider.
