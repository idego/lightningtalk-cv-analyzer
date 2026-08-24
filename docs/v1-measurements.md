# V1 hardening measurements

Evidence status: **provisional; feature remains disabled**. No live OpenAI call was made for Slice 7.

The reusable command is:

```bash
cd apps/api
PYTHONPATH=src .venv/bin/python scripts/measure_v1.py <pii-free-records.jsonl>
```

Each JSONL record uses: `mode` (`single`/`batch`/`research`), `latency_seconds`,
`status`, `input_tokens`, `output_tokens`, `web_searches`, `cache`
(`hit`/`miss`/`none`), `estimated_cost_usd`, and `evidence_kind`
(`historical_live` or `controlled_fake`). The report schema is
`v1-hardening-measurement-v1`.

Existing historical live evidence (not re-run): prompt 3108, four independent
sequential CVs, 97.5007 s total (24.3752 s/CV mean), estimated $0.0156716 total,
two valid and two fail-closed responses. This supports the provisional four-file
sequential development cap and demonstrates a material model-quality failure
rate; it does not establish production SLOs. Older recorded four-case runs range
from 76.66 s to 104.65 s and remain model-eval evidence, not load testing.

Accepted code-enforced boundaries: one 120 s model timeout, zero automatic
retries, four Web Search calls per research action, 4096 output tokens, four
files and 20 MiB per sequential batch. The batch cap is provisional. No
per-CV/per-batch dollar cap is accepted because the repository has no approved
production pricing decision or representative research workload. Cache TTL is
30 days as an operator-configurable development default, not a freshness SLA.
