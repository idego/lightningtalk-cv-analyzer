## Purpose

Defines recruiter-selected web research with citations. Each category runs through a normal synchronous request in the existing FastAPI service.

## ADDED Requirements

### Requirement: User-controlled synchronous research
The system SHALL let the recruiter start company, education/certification, and LinkedIn research separately after the base report is ready. Each selected category SHALL complete or fail within its own API request.

#### Scenario: No research selected
- **WHEN** the recruiter does not select a category
- **THEN** the system does not call Web Search for that category

#### Scenario: Research category selected
- **WHEN** the recruiter starts one category
- **THEN** the API performs only that category and returns its completed result or error

#### Scenario: Research request retried
- **WHEN** the same analysis, category, and research version are requested again
- **THEN** the system reuses a completed compatible result or safely replaces the category result without duplicates

### Requirement: Cited read-only public-web research
Research SHALL use OpenAI Web Search in read-only mode. Each result SHALL include source URLs, access times, evidence, confidence, and an `insufficient_evidence` outcome when needed.

#### Scenario: Relevant public evidence found
- **WHEN** research finds evidence about a CV claim
- **THEN** the result cites the source and explains how it relates to the claim

#### Scenario: Evidence cannot be found
- **WHEN** research finds too little reliable evidence
- **THEN** the result records the missing evidence and the searches performed

### Requirement: Requested company-presence checks
Company research SHALL check whether organizations exist, what they do, where and when they operated, their official websites, public company pages, available registries, and employer/client/project relations. It SHALL flag limited or missing detectable online presence without claiming that the company is fraudulent or a shell company.

#### Scenario: Company has a public footprint
- **WHEN** research finds reliable public evidence for a company
- **THEN** the result shows the evidence, company activity, dates, and location

#### Scenario: Company has little detectable public presence
- **WHEN** the allowed searches find no reliable website, company page, or registry record
- **THEN** the result includes a visible limited-online-presence flag, the searches performed, and the limits of that conclusion

### Requirement: Requested education checks
Education research SHALL check whether institutions, programs, degrees, and certificates exist and identify relevant dates, city, country, and accreditation when available. It SHALL highlight a location that appears inconsistent with the rest of the CV for manual review.

#### Scenario: Institution or credential researched
- **WHEN** research checks an institution, program, degree, or certificate
- **THEN** the result separates supporting, conflicting, and missing evidence

#### Scenario: Institution location differs from the rest of the CV
- **WHEN** cited evidence places the institution in a country not otherwise explained by the CV
- **THEN** the result shows the location difference and its evidence for recruiter review

### Requirement: Requested LinkedIn discovery and completeness checks
LinkedIn discovery SHALL search by candidate name and, when useful, company or role from the CV. It MUST NOT claim identity. For possible public profiles it SHALL report match evidence, whether a photo is visible, and whether a public connection or follower count is visible. Missing photo data or a visible count below the configured threshold SHALL produce the requested profile-completeness flag.

#### Scenario: Potential profiles found
- **WHEN** LinkedIn discovery finds plausible profiles
- **THEN** the system shows them as possible matches with evidence
- **AND** waits for recruiter confirmation before it treats profile-to-CV differences as relevant

#### Scenario: Completeness data is visible
- **WHEN** a possible public profile exposes photo or connection information
- **THEN** the result records the presence or absence of those elements without analyzing appearance
- **AND** shows the requested completeness flag when the configured criteria are not met

#### Scenario: Completeness data is unavailable
- **WHEN** the public result does not expose a photo or connection count reliably
- **THEN** the corresponding value is unknown and the system does not guess it

#### Scenario: No plausible profile found
- **WHEN** the allowed searches find no plausible profile
- **THEN** the report includes the requested `linkedin_not_found` flag and states that search failure does not prove the profile does not exist

### Requirement: Research outside the verdict path
Research results MUST NOT change the deterministic score or band. They MUST NOT trigger a hiring decision.

#### Scenario: Research conflicts with a CV claim
- **WHEN** cited research conflicts with the CV
- **THEN** the system shows the conflict for human review without changing the band

### Requirement: SQLite research persistence and cache
The system SHALL store completed category results in the existing SQLite persistence layer. It SHALL cache reusable company, institution, program, and certificate research without mixing candidate data.

#### Scenario: Reusable entity research exists
- **WHEN** a current compatible SQLite cache entry exists for the same normalized public entity
- **THEN** the system can reuse it and records the cache use

#### Scenario: LinkedIn research performed
- **WHEN** the system stores LinkedIn discovery or comparison
- **THEN** the result stays within the candidate analysis that requested it
