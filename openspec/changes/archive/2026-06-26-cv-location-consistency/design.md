## Context

Greenfield project. Recruiters receive CVs in batch (no candidate-facing session, no live signals like IP/timezone/device). The business needs to flag candidates whose stated location is inconsistent with their CV, for three motives: remote-work anti-fraud, right-to-work/sanctions/tax screening, and CV data-quality.

Hard constraint established during specification: **a batch CV cannot prove physical location.** The system therefore performs *consistency analysis* — comparing the location stated in the CV against independent circumstantial evidence in the same document — and outputs decision support for a human reviewer. It never auto-rejects.

## Goals / Non-Goals

**Goals:**
- Extract a candidate's claimed location and all location-bearing evidence from a text-extractable PDF/DOCX CV.
- Produce a reproducible, explainable, four-band consistency report (green/amber/red/gray).
- Keep verdict logic fully deterministic and auditable (no ML/LLM in the decision path).
- Run all enrichment offline; expose a FastAPI service; persist minimally with a full audit trail.

**Non-Goals:**
- Proving or verifying actual physical location.
- Automated rejection or any adverse automated decision.
- OCR/scanned CVs, non-English CVs, live online enrichment, structured-field claim source, ATS connector. (All deferred.)

## Decisions

### D1: Consistency analysis, not verification
Frame the output as decision support. **Why:** no honest signal in a batch CV proves location; claiming otherwise creates legal exposure under motive (b). Alternative (live verification) rejected — we don't control a candidate-facing session.

### D2: Claim parsed from CV body (not a structured field)
Identify the header/contact-block location as the claim under test; treat employer/education/other locations as evidence. **Why:** no structured field exists today. **Trade-off:** weaker than an external claim (the candidate controls both sides) — recorded as a standing recommendation to add a structured field later.

### D3: Pure deterministic rules + gazetteer (no LLM)
Extraction uses `phonenumbers`, regex/pattern detectors, and a GeoNames-style gazetteer with positional patterns instead of neural NER. **Why:** reproducibility and audit defensibility for a legally-sensitive decision; zero LLM cost. **Alternative considered:** hybrid LLM-extraction + rules-scoring — rejected to keep the entire pipeline deterministic and offline.

### D4: Config-driven weighted sum, no veto
Each signal casts a weighted vote for/against the claim, normalized to 0–100; weights live in a config file. **Why:** chosen by stakeholder for simplicity over a strong-signal veto. **Trade-off:** without a veto, a single decisive conflict could be outvoted by weak agreements unless strong weights dominate the weak pool — mitigated by calibration (see Risks).

### D5: Four bands including "gray = insufficient evidence"
green / amber / red / gray. **Why:** a sparse CV has nothing to contradict the claim; scoring it "green" is backwards. Gray routes to a human, never silently passes. Bias toward flagging when uncertain since a human reviews everything and missed fraud is costlier than a false flag.

### D6: Offline-only enrichment
`phonenumbers` (offline) + static TLD→country table. **Why:** server-side service + minimal-retention posture; no third-party PII exposure, no API keys/rate limits. Online checks (MX, address validation) reserved for an explicit opt-in module later.

### D7: Library-first, FastAPI wrapper
Pure library core (`text + claim → report`) wrapped by FastAPI (single upload + batch). **Why:** the core is reusable by a future ATS connector without rewrite; Python has the strongest batch-CV toolchain.

### D8: Minimal retention + immutable audit log + ruleset versioning
Store findings + score + ruleset/weights version; immutable audit log (input hash + ruleset version + output); national ID as `present/type` only. **Why:** if a candidate is ever disadvantaged, we must reproduce exactly what was flagged and why; raw national IDs must never be retained.

## Risks / Trade-offs

- **Weak-signal stacking / strong-signal drowning (no veto)** → Set strong-signal weights high enough to dominate the entire weak pool alone; validate with a calibration pass against real + synthetic CVs before production weights are locked.
- **Claim mis-identification (CV-against-itself)** → Use conservative positional rules for the claim; when the claim location can't be confidently identified, return gray rather than guessing.
- **Gazetteer ambiguity (e.g. "Paris, TX" vs "Paris, FR"; common city names)** → Prefer country/region resolution with explicit disambiguation hints; record ambiguity as a finding, never a silent pick.
- **PDF/DOCX extraction noise** → Restrict v1 to text-extractable files; reject scanned/empty-text inputs explicitly (not silently treated as sparse).
- **PII handling** → National ID detected as boolean/type only; configurable retention; outputs stamped as decision-support.

## Migration Plan

Greenfield — no migration. Rollout phases: (1) library core + scorer + config weights + ruleset versioning, (2) gazetteer + claim identification, (3) FastAPI wrapper + audit log + JSON contract, (4) calibration pass to set production weights.

## Open Questions

- Source of calibration CVs: real samples (incl. known-mismatched) vs synthetic fixtures.
- Concrete strong-vs-weak weight values (resolved during calibration phase).
- Retention window default (to be aligned with the consuming ATS).
