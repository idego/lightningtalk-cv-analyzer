# Scoring calibration proposal: 0–100 and four bands

Status: design for calibration only. This document does not authorize changes
to `weights.yaml`, thresholds, the scoring engine, or runtime reports. The
fresh recruiter decision export is still required before acceptance.

## Objective and boundary

The score measures consistency between an explicit candidate location claim
and independent, code-owned facts. It does not measure candidate quality,
identity, honesty, nationality, work eligibility, or recruitment risk. AI
facts, AI findings, AI prose, model confidence, and missing AI findings never
vote. Research remains reviewer support unless a later proposal defines a
separate deterministic confirmation contract and receives approval.

An analysis is `gray` before arithmetic when ingestion failed, required code
checks did not complete, the claimed person location is unresolved, or the
coverage gate is not met. Zero findings does not bypass this gate.

## Evidence matrix

| Category | Candidate severity/weight | Required source and rule | Score impact in this proposal |
| --- | ---: | --- | --- |
| Valid person-owned international phone country | strong / 35 | Code validates the full number, resolves one country without a default-region guess, and compares it with the explicit person-location claim | Eligible after acceptance calibration |
| Explicit person-address country | strong / 30 | A separately stated current/home/contact address resolves unambiguously to a country; it is not the same span as the claim | Candidate for a new code-owned extractor and anonymous fixtures before eligibility |
| Person-owned postal country | medium / 20 | A separately stated person postal code maps to one country under a reviewed versioned reference; shared formats, employer addresses, and ambiguous formats are excluded | Candidate only; currently informational and unweighted |
| Repeated explicit person-location statement | medium / 15 | A second, non-overlapping current/home/contact statement resolves independently; duplicate copies of one header block count once | Candidate only; must prove useful independence in calibration |
| Employer, client, office, project, or education location | none / 0 | These facts describe organizations or activities, not the candidate's current location | Informational only |
| Right-to-work, citizenship, national ID, language, spelling, date format, currency, email TLD | none / 0 | These are eligibility, administrative, or weak proxy facts | Informational only; never location votes |
| Candidate name, surname spelling, photo, profile count, public footprint | none / 0 | Protected or unreliable proxies | Never a finding or score input |
| AI findings/prose and company, education, or LinkedIn research | none / 0 | Model/research authority is outside the deterministic verdict | Reviewer support only |

The numeric weights are grid-search starting points, not runtime values. No
category becomes eligible merely because it appears in this table.

## Independence and deduplication

1. The claimed location is the comparison target and never votes for itself.
2. Evidence must be person-owned, exact-source anchored, code-owned, and
   unambiguous. Unknown evidence abstains; it does not conflict.
3. One semantic fact votes once. Repeated headers, copied address lines,
   equivalent phone renderings, and overlapping postal/address spans are
   deduplicated by normalized value, subject, relation, and source span.
4. Multiple phones form one phone-country category. They vote only when every
   valid person-owned resolved phone agrees; otherwise the category abstains
   and produces an ambiguity note.
5. Address and postal evidence from the same literal address block form one
   independence group and contribute at most the larger approved weight.
6. Employer, education, project, profile, and candidate evidence cannot be
   relabelled as person-location evidence to satisfy coverage.

## Coverage gate

Arithmetic is eligible only when all required code checks completed, exactly
one explicit person-location claim resolved, and at least two independent
eligible evidence groups produced a supported or conflicting comparison.
Otherwise the band is `gray`, even with zero findings or a nominal score.

For calibration reports, keep a diagnostic deterministic score when useful,
but show it as `not assessed` with a gray band until coverage passes. A failed
AI stage or another required incomplete stage also makes the displayed overall
status gray. The completed deterministic report and its diagnostic arithmetic
remain available and unchanged.

## Candidate arithmetic and bands

For eligible comparisons only:

```text
score = round(50 + 50 * (support_weight - conflict_weight) / total_weight)
```

Clamp to 0–100. Abstentions and informational notes do not enter
`total_weight`.

Candidate bands for calibration:

- `green`: 80–100, no strong conflict, coverage passed;
- `amber`: 40–79, or any single material conflict that does not meet red;
- `red`: 0–39 with at least one strong conflict, or two independent strong
  conflicts after calibration confirms that override;
- `gray`: failed, incomplete, unresolved claim, insufficient independent
  evidence, or coverage gate failure.

Borderline values go to the more review-oriented band. A red band is a review
priority, never an automated rejection.

## Anonymous worked scenarios

| Scenario | Evidence | Candidate result |
| --- | --- | --- |
| A | Claim DE; valid person phone DE; separate current address DE | 100, green |
| B | Claim DE; phone PL; separate address DE | about 50, amber |
| C | Claim DE; phone PL; separate address PL | 0, red candidate; human review required |
| D | Claim DE; no phone; employer in DE; education in PL | Gray: employer and education do not satisfy coverage |
| E | Claim DE; no findings; one supporting phone | Gray: zero findings cannot replace the second independent group |
| F | Name changes; all other facts are identical | Findings, score, band, and eligibility unchanged |
| G | AI fails after deterministic phone and address checks complete | Overall status is gray/incomplete; the deterministic diagnostic score remains available and unchanged |

## Calibration on the 16-CV acceptance set

1. Import the fresh manual-decision export. Do not use suggested decisions or
   raw HR comments as final labels.
2. Convert each accepted decision into an anonymous row containing only
   category, direction, independence group, coverage state, and expected review
   outcome. Keep source CV text and names out of tracked fixtures.
3. Have two reviewers resolve every changed, missing, and rejected matrix item.
   Record adjudication without demographic or hiring-outcome labels.
4. Freeze eligible-category definitions. Run a small documented grid over
   candidate weights and thresholds; do not tune extractors and thresholds on
   the same held-out row.
5. Because 16 cases are small, report every case and use leave-one-out
   sensitivity. Show confusion matrices for gray coverage and green/amber/red
   review priority, plus the result of name-only mutations.
6. Select the simplest candidate that meets all acceptance criteria. Submit a
   separate runtime checkpoint with the anonymous matrix, proposed config diff,
   and rollback rule.

## Acceptance and rejection criteria

Accept a runtime proposal only if:

- every AI-failed, otherwise incomplete, unresolved-claim, or below-coverage case is gray;
- no case becomes green solely because it has zero findings;
- candidate-name mutations leave findings/counts/score/band unchanged;
- AI success, failure, prose, or confidence cannot change deterministic output;
- all recruiter-accepted material conflicts are amber or red;
- the 16-case set has zero false-red cases and every red has exact evidence
  from approved independent categories;
- leave-one-out analysis does not move more than one case by more than one
  adjacent band;
- every eligible category has anonymous positive and conflict coverage, and
  the scoring rules remain reproducible from versioned code-owned evidence.

Reject or defer the runtime change if the manual export is missing, any target
band has no accepted examples, a category lacks both support and conflict
examples, a proxy is required to achieve coverage, red precision is below
100% on this small set, or materially different candidates perform equally
well. In those cases keep the current runtime unchanged and expand anonymous
calibration data.

## Magdalena backlog coverage

This proposal supports the existing backlog cards for location flags, the
complete per-candidate checklist, and visible JSON/HTML score and status. It
keeps company checks, education checks, and LinkedIn checks as separate
informational research cards rather than verdict votes. It also preserves the
requested phone/location review path while rejecting name/profile/public-
footprint proxies. This mapping is design coverage only; it does not claim
Magdalena's or another stakeholder's acceptance.

## Decisions required before runtime work

1. Approve which new code-owned evidence categories should be implemented and
   anonymously calibrated: explicit person address, postal country, and/or a
   second explicit person-location statement.
2. After the fresh export, decide whether the acceptance set contains enough
   independently labelled green, amber, red, and gray cases. If not, approve a
   larger anonymous calibration set instead of selecting thresholds.
3. Approve or reject the proposed red policy: score below 40 plus a strong
   conflict, with a possible two-independent-strong-conflicts override.
