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


### Requirement: Contact section shows literal CV contact values
The CV overview Contact section SHALL show the candidate name, first phone number, first email address, and every literal link extracted from the CV that is not inside an employment, education, or certificate section, deduplicated by normalized URL. The analysis SHALL tag each link with its section, derived from the validated records' evidence blocks extended to the next section header. Link rows SHALL render on one line with an ellipsis and expose the full literal value on hover. Each link SHALL be tagged `linkedin`, `github`, or `personal`; any host that is not LinkedIn or GitHub is `personal`. Extraction SHALL accept schemed or `www.` URLs for any host, and schemeless LinkedIn or GitHub links that carry a path (for example `linkedin.com/in/...`); other schemeless domains are not treated as links.

#### Scenario: CV lists a schemeless LinkedIn link
- **WHEN** the CV text contains `linkedin.com/in/<handle>` without `https://` or `www.`
- **THEN** it is extracted, tagged `linkedin`, and shown in the Contact section Links SHALL display the literal CV text, open in a new tab with a referrer-protecting relationship, and MUST NOT be fetched, inspected, or verified by the system.

#### Scenario: CV contains a personal website
- **WHEN** the CV contains a URL whose host is neither LinkedIn nor GitHub
- **THEN** the Contact section shows it as a personal website link with the literal CV text

#### Scenario: Project link under an employment record
- **WHEN** a GitHub link appears in a description bullet under an employment record
- **THEN** it is tagged `employment` and is not shown in the Contact section

#### Scenario: Same link appears twice
- **WHEN** the same normalized URL is extracted from two places in the CV
- **THEN** the Contact section shows it once

### Requirement: Compact overview and research controls
Education and employment overview records SHALL use two columns at desktop widths and one at mobile widths, preserving their existing order. Certifications SHALL remain a separate full-width group with Google actions aligned to its right edge. Research confidence SHALL use three dots with a localized tooltip and accessible name, without a visible text badge. Back, Copy link, and Show/Hide CV SHALL have visible outlines. Existing preview visibility and workspace breakpoints remain unchanged.
