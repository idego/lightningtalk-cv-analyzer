## ADDED Requirements

### Requirement: Project Structural Audit V1 from shared annotations

Structural timeline parsing SHALL consume the shared section and date-range annotations produced for document understanding. For equivalent source, snapshot, and parser versions, the serialized `structural-audits-v1` payload SHALL remain byte-compatible and SHALL NOT add document-understanding record IDs or fields. The separate `document-understanding-v1.timeline_record_links` collection SHALL map existing Structural Audit timeline entry IDs to structured record IDs for new reports.

The compatibility `audit_document` entry point MAY remain for one release but MUST delegate to the shared annotations when they are available rather than reparse source headings and dates.

#### Scenario: Existing structural report is projected
- **WHEN** shared annotations represent a timeline previously handled by Structural Audit V1
- **THEN** the Structural Audit payload retains its existing shape, entry IDs, observations, evidence, ordering, and snapshot behavior

#### Scenario: UI needs an entity relationship
- **WHEN** a new report associates a timeline entry with a structured education or employment record
- **THEN** the relationship is stored in document understanding rather than added to Structural Audit V1
