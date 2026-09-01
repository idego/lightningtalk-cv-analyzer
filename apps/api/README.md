# CV Analyzer API — Docling + Luna

This variant installs `DoclingLunaAnalysisStrategy` as the default producer of
the `base-analysis-v2` contract. It accepts text-layer PDF and DOCX uploads,
projects a real Docling document into evidence blocks, runs three parallel Luna
specialists, validates their candidates, and applies a sequential reviewer
before deterministic report assembly. With AI disabled, conversion and
mechanical extraction still run and the unavailable Luna passes are explicit.

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
