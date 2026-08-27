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
