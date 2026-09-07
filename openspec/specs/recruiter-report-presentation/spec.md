# recruiter-report-presentation Specification

## Purpose
Defines recruiter-facing report presentation that prioritizes supported
evidence, calibrated uncertainty, neutral context, and readable source links.

## Requirements

### Requirement: Recruiter-facing output omits implementation provenance
The report UI SHALL NOT present code-owned, AI-added, unknown-field, institution-status, or accreditation-status badges as recruiter findings or overview labels. Base-analysis findings SHALL present the observation, why it matters, what to check, and supported evidence without confidence badges.

#### Scenario: Accepted and enriched facts are displayed
- **WHEN** the report contains code-owned values, AI additions, unknown fields, institution status, or accreditation metadata
- **THEN** the recruiter-facing report omits those provenance/status badges while retaining the supported fact content

### Requirement: Evidence links use readable identities
Every displayed research source SHALL be a safe external link labeled with a readable supplied title or normalized hostname. The UI MUST NOT label sources as `Source 1`, `Source 2`, or another ordinal-only name.

#### Scenario: Source has no supplied title
- **WHEN** a research source contains only an eligible HTTPS URL
- **THEN** the link label uses its normalized hostname and the link remains keyboard accessible

### Requirement: EU status is neutral overview information
Inside/outside-EU classification SHALL appear as a separate informational row in the CV overview and MUST NOT create an attention or worth-knowing finding by itself. The row MUST state that it classifies supplied CV information and does not determine residence, nationality, or work eligibility.

#### Scenario: Mechanical evidence points outside the EU
- **WHEN** the accepted declared-location or phone evidence is classified outside the EU
- **THEN** the overview shows a neutral outside-EU row and no outside-EU finding is added

### Requirement: Postal consistency uses locality and country
When the offline postal resolver returns a supported result, the CV overview SHALL state whether the postal code is consistent with the accepted locality and country. Missing reference data or ambiguous evidence MUST remain unavailable or inconclusive and MUST NOT be presented as a mismatch.

#### Scenario: Postal code resolves to the stated locality and country
- **WHEN** accepted postal, locality, and country evidence matches one offline reference record
- **THEN** the overview shows a neutral consistent postal result

#### Scenario: Postal reference data is unavailable
- **WHEN** no configured offline reference data can evaluate the accepted postal code
- **THEN** the UI does not claim either consistency or mismatch

### Requirement: Report hierarchy uses consistent typography
Report and research sections touched by this change SHALL reuse the existing heading, body, secondary, and action styles with no additional arbitrary font sizes or semantic colors. Redundant action text MAY be replaced by an accessible icon and tooltip when the meaning remains clear.

#### Scenario: Multiple research cards are scanned
- **WHEN** company, education, and LinkedIn research sections are displayed together
- **THEN** equivalent headings, metadata, and actions use consistent visual hierarchy

### Requirement: Per-report AI cost badge
An owner-opened persisted report SHALL show a compact estimated AI cost badge backed by the owner-scoped usage endpoint. The badge SHALL use a cost-signaling icon, show USD and PLN rounded to two decimals in the compact view, and expose five-decimal detail in its tooltip. It is accounting context, not a quality or hiring signal.

#### Scenario: Report usage is available
- **WHEN** a recruiter opens their persisted analysis and usage has been ledgered
- **THEN** the report header shows the compact two-decimal estimated cost and a five-decimal tooltip detail
