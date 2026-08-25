# V1 hardening measurements

Evidence status: **local development accepted; production approval remains open**.

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

Live local Docker evidence from 2026-08-24 uses prompt 3202 and the same
Responses API path as the application:

- one held-out DOCX through `web -> api -> OpenAI`: 31.60 s, 4,165 input
  tokens, 3,323 output tokens, estimated USD 0.004821, zero request failures;
- one two-file batch through the same path: 26.93 s total, 7,573 input tokens,
  3,118 output tokens, estimated USD 0.005256, 2/2 successful results;
- combined application sample: three CVs, 11,738 input tokens, 6,441 output
  tokens, estimated USD 0.010077, zero failures;
- the accepted four-case prompt eval: 78.57 s, estimated USD 0.014226, 100%
  semantic recall, 100% finding and line evidence accuracy, zero unsupported
  findings, and two manually reviewed non-attention noise findings.

Accepted V1 boundaries remain one 120 s model timeout, zero automatic retries,
four Web Search calls per research action, 4,096 output tokens, four files and
20 MiB per sequential batch. The measurements do not justify a queue or worker
service. Local validation uses a USD 1 soft budget and USD 2 hard stop. The
application bounds spend through file, output-token and Web Search limits;
provider-side project budgets remain the hard production safeguard because an
in-process dollar check cannot undo a completed request. Cache TTL is 30 days
as an operator-configurable development default, not a freshness SLA.
