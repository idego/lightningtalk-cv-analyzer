# AI document eval

Inputs, expectations, deterministic observations, raw responses, and reports
live under gitignored `data/ai-eval/`. The runtime request builder and this
harness share the single tracked prompt/schema source in
`apps/api/src/cv_validator/ai/contracts/`.

Run the four-case baseline with the authenticated Codex model transport:

```bash
python scripts/eval_ai_document.py run \
  --manifest data/ai-eval/manifest-2108.json \
  --backend codex \
  --model gpt-5.6-luna \
  --reasoning medium \
  --confirm-live-model-run \
  --output data/ai-eval/results/baseline-3108.json
```

The command rejects manifests with more than four cases and processes accepted
cases sequentially in fresh contexts. Every case supplies one or more private
page files with stable page IDs plus a private
`deterministic-observations-v1` JSON file. The command validates the complete
Draft 2020-12 output schema and records expected-finding recall, unsupported
findings, unexpected findings, page-aware exact evidence for findings and for
all facts/findings/research candidates, latency, usage, and explicitly
configured estimated cost. Aggregate acceptance uses micro recall and micro
evidence exactness; the per-case macro recall remains diagnostic only. It prints
a safe start/completion line for each anonymous case so a live run does not
look stalled. Recall is not precision.

The AI input marks every canonical redacted source line with a stable,
page-scoped `line_id`. Model output cites `page_id` plus `line_id` and sets
`excerpt` to `null`; code rejects unknown, cross-page, irrelevant, or
model-authored evidence and materializes the exact redacted line text. A stored
materialized result can be re-scored only when its excerpt still matches that
canonical line.

The strict acceptance gate requires all four responses to pass schema and
protected-boundary validation, 100% expected-finding recall, 100% page-aware
exact finding evidence, zero unsupported findings, and zero forbidden outputs.
Every unexpected finding must be reviewed by index. Only `true positive` and
`przydatne „warto wiedzieć”` additions are accepted; duplicates,
overinterpretations, and parsing/flattening artifacts fail the gate. One
finding can satisfy at most one expected finding.

Re-score a stored response without another model call and attach an approved private manual review:

```bash
python scripts/eval_ai_document.py rescore \
  --manifest data/ai-eval/manifest-2108.json \
  --input data/ai-eval/results/baseline-3108.json \
  --output data/ai-eval/results/baseline-3108.json
```

`--manual-review <private-markdown-path>` remains available when a future benchmark produces additional findings that require human classification; no manual-review file is needed for the accepted baseline.

The manifest, stored responses, manual review, and every output path are required to resolve under the gitignored `data/ai-eval/` directory. The runner refuses paths outside it.

The Codex backend has no supported output-token cap in this harness. Its report
therefore records `max_output_tokens: null` and
`output_limit_enforcement: not_enforced`; passing `--max-output-tokens` does not
change that metadata or claim enforcement.

Use `--backend responses` with `OPENAI_API_KEY` only after separate coordinator
approval for live calls. For Responses, `--max-output-tokens` and the explicit
`--confirm-live-model-run` acknowledgement are mandatory, and the report marks
the limit as `enforced`. The runner performs no automatic retries, uses a
120-second timeout, sets `store=false`, and sends no tools. Optional explicit
token prices make the estimate reproducible. No path under `data/` may be added
to Git.

Each private manifest case has this input shape:

```json
{
  "id": "private-case-id",
  "pages": [
    {"page_id": "page-0001", "input": "case/page-0001.txt"}
  ],
  "deterministic_observations": "case/observations.json",
  "expected_findings": [],
  "forbidden_output_terms": []
}
```

The observations file must contain `contract_version`,
`deterministic_ruleset_version`, and an `observations` array. All referenced
files must resolve under ignored `data/ai-eval/`.

## Business coverage

This matrix is the anonymous product contract derived from the approved roadmap. It contains no CV text, reviewer comments, names, or expected results.

| Backlog need | Primary owner | Required output or check |
| --- | --- | --- |
| Phone and stated city/address extraction | document prompt | Structured contact facts with source evidence and explicit unknowns |
| Institution, program, and study dates | document prompt | Structured education facts with source evidence |
| Company, role, and employment dates | document prompt | Structured employment facts with source evidence and relationship type |
| Non-EU phone-country flag | fixed signal | Offline phone parsing; informational, never identity or work-eligibility proof |
| Locality existence, country, and atypicality | fixed signal | Offline reference-data result or explicit unresolved state |
| Combined outside-EU location flag | fixed signal | Phone plus stated-location observations and limitation |
| Possible LinkedIn profiles | research check | Candidate-scoped possible matches; recruiter confirmation required |
| Visible photo and public connection count | research check | Availability only; no appearance analysis; unavailable stays unknown |
| No plausible LinkedIn profile found | research check + explicit test | Searches and limitations; absence is not proof |
| Institution existence and location | research check | Cited supporting, conflicting, or insufficient evidence |
| Company existence and online presence | research check | Separate entity existence from person-company relationship |
| Company has little detectable public presence | research check + explicit test | Searches and limits; never label a company fraudulent |
| Complete flag checklist | UI result + explicit test | All fixed, document-AI, and research flags with source and reason |
| Per-candidate JSON and readable HTML | UI result + explicit test | One report model rendered in both representations |

Cross-cutting prompt and test rules: findings require a page/source excerpt; missing data is not suspicious by itself; demographic proxies, appearance, nationality inference, hiring recommendations, and unsupported verification claims are forbidden; AI and research never change the deterministic score or band.

## Anonymous finding taxonomy

Version: `finding-taxonomy-v1`

The private corpus was used only to identify recurring classes below. No source CV, HR comment, identity, employer combination, or reconstructable expected result is retained here.

| Category | Emit when | Do not infer |
| --- | --- | --- |
| `contact_conflict` | Two explicit contact facts point to different countries or values | Physical location, nationality, eligibility, or fraud |
| `missing_contact_data` | A requested phone, stated location, or public-profile URL is absent | Suspicion or negative score |
| `timeline_gap` | Adjacent dated activities leave a material unexplained interval | Unemployment or deception |
| `timeline_overlap` | Dated activities overlap and the relationship is not explained | Impossibility; study and work can coexist |
| `duration_claim_conflict` | A stated experience duration conflicts arithmetically with dated history | Intent to mislead |
| `relationship_ambiguity` | Text does not distinguish employer, client, project, marketplace, open-source project, or network participation | Employment verification |
| `document_artifact` | Literal malformed URL/email, raw markup, generator token, broken fragment, or detached layout is present | Authorship or fraud |
| `semantic_outlier` | A responsibility is materially unrelated to its surrounding role and needs review | Fabrication without corroboration |
| `internal_fact_conflict` | Two comparable statements in the CV cannot both be true as written | Which statement is correct |
| `research_needed` | A public-entity, credential, date, or possible profile claim needs optional research | The research outcome |

Reviewer-facing finding statuses are `conflicting`, `unconfirmed`, and `missing`. Consistent observations may remain in facts or the deterministic audit but are not AI findings. Importance is `attention`, `worth_knowing`, or `remaining`; confidence is `high`, `medium`, or `low`.

### Boundaries

- Analyze only literal CV content. Do not use web search, background knowledge about named entities, or HR comments.
- Evidence must be an exact substring of the submitted CV and identify a provided page ID.
- Emit one finding per material underlying problem and merge related evidence.
- A shared boundary month is not a timeline overlap. Education and work may coexist unless a concrete conflict is present.
- Normal job titles, aliases, founding titles, and missing contract labels are not relationship ambiguity by themselves.
- Flattened-input spacing, bullets, repeated page furniture, and detached layout are analysis limitations, not CV findings.
- A finding reports an observation and limitation, not identity or location verification.
- Never infer or score nationality, ethnicity, origin, appearance, religion, health, age, family status, or right to work from proxies.
- Never recommend reject/advance, calculate a hiring score, or modify the deterministic band.
- Missing LinkedIn, phone, photo, connections, or public footprint is not adverse evidence.
- Entity existence and candidate-to-entity relationship are separate questions.

### Completeness checklist

For every CV, the result must include: at most the requested phone and stated-location contact facts; one composite fact per education entry; one composite fact per employment entry; unknown markers for absent requested fields; timeline gaps/overlaps considered; duration claims considered; contact contradictions considered; relationship ambiguity considered; malformed or generated-document artifacts considered; research candidates separated by company, education/certification, and LinkedIn; every factual finding evidenced; uncertainty and flattened-input limitations stated; forbidden demographic and hiring outputs absent.
