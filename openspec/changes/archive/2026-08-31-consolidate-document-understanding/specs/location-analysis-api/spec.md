## ADDED Requirements

### Requirement: Return bounded document understanding in analysis reports

Every newly completed analysis response SHALL include a top-level `document_understanding` value conforming exactly to `document-understanding-v1`, or `null` only when understanding is unavailable or the stored report predates the capability. The API SHALL apply the same sanitizer used by persistence and SHALL NOT reconstruct a missing understanding payload from AI facts during report reads.

#### Scenario: New analysis completes
- **WHEN** the API returns a newly analyzed supported CV
- **THEN** `document_understanding` is a sanitized V1 object or a truthful unavailable state

#### Scenario: Legacy analysis is loaded
- **WHEN** a stored report predates the understanding contract
- **THEN** the API returns `document_understanding: null` and preserves all legacy report fields

#### Scenario: Stored understanding is invalid
- **WHEN** a stored understanding value fails its closed schema, bounds, cross-reference, or defense-in-depth privacy validation
- **THEN** the API suppresses that object, records only a safe error code, and preserves otherwise valid report surfaces
