# Candidate name boundary

The candidate name is a neutral extracted fact. It may be shown in the report
and used as the literal name in a candidate-scoped LinkedIn discovery query.
It is not evidence about the candidate.

The application must not use a name, surname spelling, or the absence of a
public profile to infer:

- nationality, ethnicity, origin, language, residence, or current location;
- citizenship, work permission, identity, honesty, fraud, or recruitment risk;
- a suspicious finding, review priority, score, band, rejection, or advancement.

LinkedIn discovery returns possible profiles only. A recruiter must confirm a
specific profile before comparison. A missing or ambiguous result is uncertainty,
not negative evidence. LinkedIn discovery and comparison remain outside the
deterministic verdict.

The regression test
`test_candidate_name_is_neutral_except_for_literal_linkedin_discovery_query`
changes only the name in two otherwise identical anonymous CVs. It requires the
complete deterministic payload, findings, checklist counts, score, band, and
research-category eligibility to remain unchanged. Only the accepted
`candidate_name` fact and its LinkedIn `query_subject` may change.

