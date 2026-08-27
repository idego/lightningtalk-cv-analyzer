# AI document evaluation

Private CV inputs, expected findings, model responses, and reports belong only
under the ignored `data/ai-eval/` directory. Never commit them.

The evaluator and runtime use the same prompt and response contract from
`apps/api/src/cv_validator/ai/contracts/`. Model output is checked for schema
validity, supported facts, valid page and line references, finding recall, and
unsupported findings. Code adds provenance, excerpts, checklist data, and
contract versions after validation.

Re-score an existing response without an AI call:

```bash
python scripts/eval_ai_document.py rescore \
  --manifest data/ai-eval/manifest.json \
  --input data/ai-eval/results/baseline.json \
  --output data/ai-eval/results/baseline.json
```

Run a paid evaluation only after explicit cost approval:

```bash
python scripts/eval_ai_document.py run \
  --manifest data/ai-eval/manifest.json \
  --backend responses \
  --model gpt-5.6-luna \
  --reasoning medium \
  --max-output-tokens 4096 \
  --confirm-live-model-run \
  --output data/ai-eval/results/baseline.json
```

The runner uses no web tools, stores no provider response, performs no automatic
retries, and refuses input or output paths outside `data/ai-eval/`.
