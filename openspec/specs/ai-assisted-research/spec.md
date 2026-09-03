# AI-assisted research Specification

## Purpose

Defines optional cited public-web research after a validated base analysis.

## Requirements

### Requirement: Research only accepted base-analysis subjects

Company research SHALL use accepted employment records with a supported named
organization. Education research SHALL use accepted education records with a
supported institution or certificate. LinkedIn discovery SHALL require a
supported candidate name and may use accepted organization and role fields as
search hints.

Ambiguous records, ambiguous fields, self-employment labels, skills, raw
extractor candidates, reviewer-rejected candidates, and unvalidated model
output MUST NOT become research subjects.

#### Scenario: Reviewer adds a missing supported employer

- **WHEN** the reviewer adds an employment record and the shared evidence and
  relation validator accepts it
- **THEN** the employer can become a company-research subject

#### Scenario: Technology resembles an employer

- **WHEN** a technology name is ambiguous or lacks an accepted employment
  relation
- **THEN** company research omits it

### Requirement: Automatic and manual category starts

After base analysis completes, the client SHALL start each enabled eligible
research category automatically. Company, education, and LinkedIn categories
run independently and remain available as manual actions after a failed or
disabled automatic attempt.

#### Scenario: Eligible categories exist

- **WHEN** automatic research is enabled and accepted subjects exist
- **THEN** eligible categories start without waiting for another analysis pass

#### Scenario: Research is disabled

- **WHEN** the user or deployment disables public research
- **THEN** no automatic or manual research request is made

### Requirement: Cited read-only public-web research
Research SHALL use OpenAI Web Search in read-only mode. Each result SHALL include source URLs, access times, calibrated confidence, searches performed, limitations, and an `insufficient_evidence` outcome when appropriate. Research prompts MUST define low, medium, and high confidence with conservative examples, require uncertainty to identify missing or conflicting support, and forbid high confidence based on a single weak attribute.

Research is decision support. It MUST NOT claim that a candidate is dishonest, fraudulent, physically located somewhere, or eligible to work. It MUST NOT trigger a hiring decision or mutate the accepted base analysis.

#### Scenario: Public evidence is insufficient
- **WHEN** allowed searches do not support a public claim
- **THEN** the result records insufficient evidence, low confidence, searches, and limitations

#### Scenario: Evidence conflicts with the proposed result
- **WHEN** a result has material conflicting identity or entity evidence
- **THEN** confidence is low and uncertainty names the conflict without making a verification claim

### Requirement: Company research
Company research SHALL check public evidence for organization existence, activity, operating dates, location, official pages, and registries. Missing public evidence SHALL remain inconclusive and MUST NOT be described as proof that an organization is fake. High confidence SHALL require multiple mutually consistent authoritative signals for the exact organization; a name-only search result MUST NOT receive high confidence.

Company research SHALL return each supported office as a separate map-searchable address with an optional short comment. It SHALL return operating periods as separate date fields with an optional short comment. Explanatory prose MUST NOT be placed in address or date fields.

#### Scenario: Company has limited public evidence
- **WHEN** no reliable official page or registry result is found
- **THEN** the result remains inconclusive with low confidence and explains the search limits

#### Scenario: Company has several reported offices
- **WHEN** public evidence supports more than one office
- **THEN** each office is displayed separately and links to its own Google Maps search

### Requirement: Education research
Education research SHALL check public evidence for institutions, programs, degrees, certificates, dates, and location. Accreditation MAY be retained as backend research metadata but SHALL NOT be shown as a recruiter-facing status badge. A cited institution-country difference MAY be shown for manual review but is not evidence of a false CV claim. High confidence SHALL require consistent authoritative support for the exact institution and relevant credential context.

#### Scenario: Institution country differs
- **WHEN** cited sources place an institution in another country
- **THEN** the difference is shown for review with low or medium confidence and without a dishonesty claim

### Requirement: LinkedIn discovery
LinkedIn discovery SHALL return possible public profile links with citations, calibrated confidence, visible photo status, and visible connection-count status. It MUST NOT claim identity, compare appearance, or automatically match a person. Unknown public data remains unknown.

High confidence SHALL require supported name alignment plus at least one independently supported experience or education alignment. Name-only results, results with missing experience context, and results with material conflicts MUST be medium or low. A same-name profile with wrong or conflicting experience MUST be low confidence. The default possible-profile limit is three and is configurable from 1 to 20. The default visible connection-count threshold is 500.

#### Scenario: Profile data is unavailable
- **WHEN** photo or connection-count data is not publicly supported
- **THEN** the result keeps that field unknown

#### Scenario: Same name but conflicting experience
- **WHEN** an indexed profile shares the candidate name but its supported experience conflicts with the admitted search hints
- **THEN** the possible profile is low confidence and uncertainty states the conflict

#### Scenario: Name and experience align
- **WHEN** public indexed evidence supports the candidate name and at least one admitted organization, role, or education hint without material conflict
- **THEN** the possible profile may be high confidence while remaining explicitly unverified

### Requirement: Persistence and reusable cache

Completed category results SHALL be stored under the owning analysis. Reusable
public-entity cache entries MUST exclude candidate-specific data. Every cache
hit or miss SHALL be recorded for the owning analysis, and responses SHALL
disclose whether a result came from cache.

A repeated compatible request SHALL return the stored completed result without
another provider call. Cache failures in one category MUST NOT block unrelated
categories.

#### Scenario: Compatible reusable result exists

- **WHEN** a current public-entity cache entry matches the request
- **THEN** the API reuses it and records a cache hit for the owning analysis
