# CV Analyzer API

The API is a strategy-neutral host for the `base-analysis-v2` contract.

A variant implements `AnalysisStrategy`, receives the original PDF or DOCX,
and returns a validated report. The shared checkout uses
`UnavailableAnalysisStrategy`, so analysis fails clearly until a variant is
installed.

Run tests:

```bash
PYTHONPATH=src .venv/bin/pytest -q
```

The retained shared capabilities are:

- upload and batch boundaries;
- report schema validation;
- SQLite ownership, audit, retention, and deletion;
- phone, e-mail, literal URL, postal-candidate, and e-mail typo primitives;
- GeoNames resolution infrastructure;
- company, education, and LinkedIn research with reusable cache provenance.

There is no score, band, Document Understanding, Structural Audit, ESCO,
national-ID redaction, file metadata, live link inspection, or manual retry of
the deleted monolithic analysis pass.
