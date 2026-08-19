## Purpose

Defines optional web research with citations. Research adds to a completed CV report but does not delay or change its deterministic verdict.

## ADDED Requirements

### Requirement: User-controlled research categories
The system SHALL let the recruiter start company, education/certification, and LinkedIn research separately after the base report is ready.

#### Scenario: No research selected
- **WHEN** the recruiter does not select a category
- **THEN** the system does not create a job for that category

#### Scenario: Selected categories
- **WHEN** the recruiter selects one or more categories
- **THEN** the system creates jobs only for those categories

### Requirement: Cited read-only public-web research
Research SHALL use read-only public web access. Each result SHALL include source URLs, access times, evidence, confidence, and an `insufficient_evidence` outcome when needed.

#### Scenario: Relevant public evidence found
- **WHEN** research finds evidence about a CV claim
- **THEN** the result cites the source and explains how it relates to the claim

#### Scenario: Evidence cannot be found
- **WHEN** research finds too little reliable evidence
- **THEN** the result is `insufficient_evidence` and is not a negative signal

### Requirement: Research-specific behavior
Company research SHALL check organization claims. Education research SHALL check institutions, programs, and certificates. LinkedIn discovery SHALL return possible profiles and MUST NOT claim identity.

#### Scenario: Company or education claim researched
- **WHEN** research checks a company, institution, program, or certificate
- **THEN** the result separates supporting evidence, conflicting evidence, and missing evidence

#### Scenario: Potential LinkedIn profiles found
- **WHEN** LinkedIn discovery finds plausible profiles
- **THEN** the system shows them as possible matches with evidence
- **AND** waits for recruiter confirmation before it treats profile-to-CV differences as relevant

### Requirement: Research outside the verdict path
Research results MUST NOT change the deterministic score or band. They MUST NOT trigger a hiring decision.

#### Scenario: Research conflicts with a CV claim
- **WHEN** cited research conflicts with the CV
- **THEN** the system shows the conflict for human review without changing the band

### Requirement: Safe cache reuse
The system SHALL cache reusable company, institution, and certificate research. It MUST keep candidate data within the correct report.

#### Scenario: Reusable entity research exists
- **WHEN** a current compatible cache entry exists for the same normalized public entity
- **THEN** the system can reuse it and records the cache use

#### Scenario: LinkedIn research performed
- **WHEN** the system stores LinkedIn discovery or comparison
- **THEN** the result stays within the candidate analysis that requested it
