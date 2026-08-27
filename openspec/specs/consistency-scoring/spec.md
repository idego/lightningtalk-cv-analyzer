# consistency-scoring Specification

## Purpose
Defines the deterministic, explainable location-consistency score, its evidence
gate and four review bands. AI and recruiter-triggered research remain outside
the verdict path.

## Requirements

### Requirement: Config-driven weighted scoring
The system SHALL compute a 0-100 consistency score from independent
`ScoringSignal` values created by fixed rules from validated, code-owned
location facts. Weights SHALL be read from configuration and not hard-coded.
Candidate extraction MUST NOT assign weights. A uniquely resolved
person-location claim SHALL be the comparison target and SHALL NOT vote for
itself. Eligible V1 comparisons SHALL include aggregate international phone
country and an unambiguous person-owned postal country. AI-derived facts,
associations, interpretations, and research findings MUST NOT become weighted
inputs. Every report and persisted audit record SHALL identify both the
immutable weights version and a separate immutable scoring-policy version.

#### Scenario: Signals agree with claim
- **WHEN** enough eligible code-owned facts are consistent with the code-owned
  claimed location
- **THEN** the system produces a high score reflecting that deterministic
  agreement

#### Scenario: Strong signal conflicts with claim
- **WHEN** the minimum independent-evidence requirement is satisfied and a
  strong eligible code-owned country fact conflicts with the claimed location
- **THEN** the conflict lowers the score by its configured weight

#### Scenario: Phone and postal country support the claim
- **WHEN** a unique person-location claim, aggregate phone country, and
  independently person-owned postal country resolve to the same country
- **THEN** the configured weighted score is calculated from two supporting
  comparisons
- **AND** the report receives a non-gray band according to configured thresholds

#### Scenario: One comparison conflicts
- **WHEN** the minimum evidence gate is met and one eligible country conflicts
  with the person-location claim
- **THEN** the conflict changes the score only by its configured weight
- **AND** the configured band policy classifies the result

#### Scenario: Evidence remains below the assessment minimum
- **WHEN** a unique claimed location exists but fewer independent weighted
  categories are available than the configured minimum
- **THEN** the report keeps the neutral configured base score and gray band
- **AND** preserves each supporting or conflicting comparison as an itemized
  finding without presenting a provisional verdict score in the UI

#### Scenario: Postal format is ambiguous
- **WHEN** a postal value maps to zero or multiple countries
- **THEN** it remains an informational observation
- **AND** it does not count toward score, band, or the minimum evidence gate

#### Scenario: Postal value is not person-owned
- **WHEN** a postal value belongs to an employer, education, client, project, or
  office context, or cannot be associated with the person without guessing
- **THEN** no postal scoring fact or signal is created

#### Scenario: Only AI interpretation resolves an ambiguity
- **WHEN** code-owned facts are insufficient but AI returns a plausible
  interpretation
- **THEN** the deterministic result remains gray or otherwise insufficient
- **AND** the AI value is not used as a weighted input

#### Scenario: Weights changed via configuration
- **WHEN** deterministic signal weights are updated in configuration
- **THEN** scoring reflects the new weights without code changes

#### Scenario: Scoring inputs change without approved calibration
- **WHEN** an eligible deterministic scoring input is removed or replaced and
  no separately approved calibration exists for that change
- **THEN** the configured weights, minimum evidence requirement, and band
  thresholds remain unchanged
- **AND** insufficient mechanically defensible evidence produces the
  deterministic gray outcome

### Requirement: Four-band classification
The system SHALL classify each result into exactly one of four bands: green (signals present and agree), amber (some conflict), red (strong or multiple conflict), and gray (insufficient evidence). A CV with too few signals MUST be classified gray, never green.

#### Scenario: Sparse CV
- **WHEN** the CV yields too few location signals to assess the claim
- **THEN** the system classifies the result as gray (insufficient evidence) and routes it to a human

#### Scenario: Clear conflict
- **WHEN** strong or multiple signals conflict with the claim
- **THEN** the system classifies the result as red

#### Scenario: Bias toward flagging under uncertainty
- **WHEN** the result is borderline between two bands
- **THEN** the system selects the band that routes the candidate to human review

### Requirement: Explainable, reproducible report
The report SHALL contain the deterministic score, band, candidates, code-owned facts, observations, scoring signals, and rule findings. Each deterministic result SHALL include authority, evidence, extractor version, and any applicable reference-data version. It SHALL also contain available AI document findings, research findings, a summary, evidence, authority/source labels, and the settings that produced each section. The same redacted canonical input, deterministic extractor versions, reference-data versions, and ruleset MUST produce the same deterministic score, band, facts, observations, scoring signals, and rule findings. The system SHALL make AI sections auditable through stored model, prompt, schema, deterministic-observation, and evidence data.

#### Scenario: Itemized findings
- **WHEN** the system produces a report
- **THEN** each deterministic finding shows its observed value, claimed value, direction, weight, reason, authority, source evidence, extractor version, and any applicable reference-data version

#### Scenario: Itemized AI-assisted findings
- **WHEN** AI document or research findings are available
- **THEN** each finding shows its category, importance, confidence, reason, evidence, source location or URL, authority, and configuration version

#### Scenario: Deterministic output
- **WHEN** the system analyzes the same CV twice with the same deterministic extractor, reference data, and ruleset versions
- **THEN** both runs produce the same deterministic score, band, facts, and rule findings regardless of AI output

### Requirement: Decision-support framing
The system MUST NOT auto-reject or auto-advance candidates and SHALL stamp every report as decision-support, not automated rejection.

#### Scenario: No automated decision
- **WHEN** a report is produced for any band including red
- **THEN** the system returns the report for human review and takes no adverse automated action

### Requirement: AI findings excluded from deterministic verdict
AI document and research facts, associations, interpretations, and findings MUST NOT change score weights or the four-band result. The scoring boundary SHALL accept only `ScoringSignal` values produced by fixed deterministic rules from facts explicitly marked as code-owned and validated against source evidence.

#### Scenario: AI reports a high-importance inconsistency
- **WHEN** AI marks a finding as high importance
- **THEN** the system shows it for human review
- **AND** calculates score and band only from code-owned fixed-rule facts

#### Scenario: AI returns a value that conflicts with a code-owned fact
- **WHEN** an AI-derived value differs from a code-owned deterministic fact
- **THEN** the report shows the discrepancy for human review without replacing the code-owned score input

### Requirement: Requested location signals
The report SHALL contain code-owned phone-country facts and an explicitly
person-owned stated-city-or-address result when deterministic extraction can
identify them without guessing. It SHALL resolve localities through versioned
offline reference data without treating absence from the bounded index as proof
that a place does not exist. It SHALL show separate informational observations
for an aggregate explicit phone country outside the EU and a uniquely resolved
stated location outside the EU. It SHALL show a combined outside-EU observation
only when both distinct code-owned categories are available and non-EU, and
SHALL show mixed EU/non-EU evidence separately. The project-owner-approved V1
locality-size rule SHALL classify a uniquely resolved non-EU locality as small
only when the reference population is below the configurable threshold, which
defaults to 10,000. This observation SHALL remain informational and MUST NOT
affect score or band. When reference population is unavailable, the report
SHALL instead return an informational `small_locality_not_evaluated` checklist
observation that makes no positive or negative claim. V1 MUST NOT classify a
locality as atypical. A postal value SHALL become a weighted postal-country
comparison only when it maps to exactly one country and is deterministically
owned by the person contact context. Shared, unresolved, ambiguous, and
non-person postal compatibility SHALL remain unweighted observations.

#### Scenario: Explicit phone prefix points outside the EU
- **WHEN** every deterministically person-owned, valid, country-resolved
  international phone fact maps to the same non-EU country
- **THEN** the report shows one aggregate phone-country flag with every
  supporting fact, authority, evidence, extractor version, and applicable
  reference-data version

#### Scenario: Resolved phone countries conflict
- **WHEN** deterministically person-owned phone facts map to different countries
- **THEN** the report records an ambiguous aggregate observation and creates no
  phone scoring signal

#### Scenario: Phone country requires a default region
- **WHEN** a phone country cannot be determined without assuming a default
  region
- **THEN** the report keeps the phone country unknown and does not score it

#### Scenario: Stated locality can be resolved
- **WHEN** deterministic code resolves the stated city or address to one country
- **THEN** the report shows the resolved location, reference-data version, and
  whether the stated-location outside-EU observation applies
- **AND** for a non-EU locality with a known population below 10,000 reports the
  zero-weight `small_locality_outside_eu` observation

#### Scenario: Locality is at the configured boundary
- **WHEN** a resolved non-EU locality has a population equal to the configured
  10,000 threshold
- **THEN** the report does not classify it as small

#### Scenario: Locality population is unavailable
- **WHEN** a resolved non-EU locality has no population in the bounded reference
  data
- **THEN** the report shows `small_locality_not_evaluated` without guessing its
  size

#### Scenario: Stated locality cannot be resolved
- **WHEN** deterministic code cannot find the stated locality in the bounded
  offline index or cannot map it to one country
- **THEN** the report shows an unresolved or ambiguous location observation with
  the attempted value and does not guess its country or claim the place is
  nonexistent

#### Scenario: Unique person-owned postal country is available
- **WHEN** a postal value maps to exactly one country and its evidence is owned
  by the person contact context
- **THEN** the report creates a versioned postal-country fact and eligible
  scoring signal

#### Scenario: Postal compatibility is present
- **WHEN** deterministic extraction records postal compatibility that is not an
  eligible unique person-owned postal-country fact
- **THEN** the report shows it as an observation with zero scoring weight
- **AND** score and band remain unchanged by that observation

#### Scenario: Postal compatibility is not eligible for scoring
- **WHEN** a postal value is shared, unresolved, ambiguous, or belongs to an
  employer, education, client, project, or office context
- **THEN** the report keeps any available compatibility information unweighted
- **AND** score and band remain unchanged by that observation

#### Scenario: Location signals are combined
- **WHEN** a unique code-owned stated-location fact and an aggregate person-owned
  phone-country fact are both available and both are non-EU
- **THEN** the report includes a combined outside-EU observation with both
  evidence items and a disclaimer that they do not prove nationality, identity,
  physical presence, work eligibility, or fraud

#### Scenario: EU membership evidence is mixed
- **WHEN** a unique code-owned stated-location fact and an aggregate person-owned
  phone-country fact fall on different sides of the versioned EU member-state set
- **THEN** the report includes a conflicting informational
  `mixed_eu_location_evidence` observation and does not emit the combined
  outside-EU observation

### Requirement: Visible deterministic context
The report SHALL expose every available code-owned person-location,
phone-country, and postal-country fact even when the assessment remains gray.
The recruiter UI SHALL show available deterministic facts and SHALL distinguish
inside-EU, outside-EU, mixed, and unknown evidence without claiming nationality,
residence, work permission, or physical presence. It SHALL present compact
location consistency only after the configured minimum evidence gate is met and
MUST NOT present the gray diagnostic numeric score as a completed assessment.

#### Scenario: Polish contact facts agree
- **WHEN** the CV states a uniquely resolved Polish person location and contains
  a valid Polish phone and uniquely Polish person-owned postal code
- **THEN** the overview shows Poland for phone and postal country
- **AND** shows that the available location evidence is consistent and inside
  the EU

#### Scenario: Sparse deterministic evidence remains visible
- **WHEN** available phone, postal, or person-location facts do not meet the
  minimum evidence gate
- **THEN** the overview keeps the available facts visible
- **AND** does not show a recruiter-facing numeric consistency assessment
