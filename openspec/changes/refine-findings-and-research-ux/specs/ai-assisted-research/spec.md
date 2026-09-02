## MODIFIED Requirements

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

#### Scenario: Company has limited public evidence
- **WHEN** no reliable official page or registry result is found
- **THEN** the result remains inconclusive with low confidence and explains the search limits

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
