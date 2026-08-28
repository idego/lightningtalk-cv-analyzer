## ADDED Requirements

### Requirement: Source research eligibility from the validated subject projection

Company and education research requests SHALL consume a derived bounded request projection produced from immutable code-owned research subjects followed by independently validated AI additions. They MUST NOT require a successful document-analysis outcome when public research remains enabled and the requested public entity is already supported by code-owned source evidence. They MUST remain unavailable when the user or deployment disables the overall AI/public-research feature. Document-AI failure or omission and AI/public-research authorization are separate states.

The persisted document-understanding contract SHALL contain only immutable `code_research_subjects`. Each request SHALL derive its union without modifying that contract, allocate the category limit to code-owned subjects first in stable source order, then add deduplicated AI subjects up to the remaining capacity, and use exact dedupe keys of category plus Unicode-normalized, whitespace-collapsed, case-folded subject. AI retry MAY change only the derived request union; it MUST NOT change or reorder persisted code subjects. Reusable-cache isolation, candidate-PII exclusion, and existing category limits SHALL apply to the derived request.

LinkedIn discovery SHALL retain its existing candidate-scoped behavior and MUST NOT be generated from skill, education, or organization section extraction alone.

#### Scenario: Code supplies all education subjects after document-AI failure
- **WHEN** code-owned understanding extracts supported institution entries, public research remains enabled, and document AI is unsuccessful
- **THEN** the recruiter can start education research for the bounded code-owned subjects

#### Scenario: User disables AI and public research
- **WHEN** the user or deployment disables the overall AI/public-research feature
- **THEN** company, education, and LinkedIn research remain unavailable even when code-owned subjects exist

#### Scenario: Code supplies a named employer
- **WHEN** code-owned understanding extracts a supported named organization from employment
- **THEN** company research can use that organization without requiring an AI-generated research candidate

#### Scenario: Generic relationship label is present
- **WHEN** an entry contains only a self-employed or freelance relationship label
- **THEN** the subject projection and company research request omit that label

#### Scenario: AI adds a distinct supported subject
- **WHEN** independently validated AI field evidence supports a distinct public entity omitted by code
- **THEN** the bounded request may include that AI-derived subject with its authority preserved

#### Scenario: Subject limit is reached
- **WHEN** the number of code-owned and AI-derived subjects exceeds the existing category limit
- **THEN** code-owned subjects consume the limit first in stable source order and AI additions cannot displace them
