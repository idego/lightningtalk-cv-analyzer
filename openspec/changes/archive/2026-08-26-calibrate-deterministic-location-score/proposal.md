# Calibrate deterministic location score

## Why

The current runtime requires two independent deterministic evidence categories,
but only phone-country comparison can enter the scorer. Typical CVs therefore
remain gray even when a uniquely resolved stated location, international phone,
and person-owned postal code agree.

## What changes

- Promote an unambiguous, person-owned postal country to a versioned code-owned
  fact and scoring signal.
- Compare phone country and postal country independently with the resolved
  person-location claim using configured weights.
- Keep shared, unresolved, non-person, and ambiguous postal values informational.
- Preserve gray for genuinely insufficient evidence without presenting its
  internal diagnostic score as a completed assessment in the UI.
- Show phone country, postal country, location consistency, and inside/outside-EU
  context in the recruiter-facing overview when the required evidence exists.

## Non-goals

- AI, company, education, LinkedIn, names, appearance, spelling, and employer or
  education locations do not enter score or band calculation.
- This change does not alter architecture, persistence topology, or research.
