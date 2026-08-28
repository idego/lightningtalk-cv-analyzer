"""Structural Audit V1 compatibility wrapper over document understanding."""
from __future__ import annotations

from cv_validator.ingestion import RedactedDocument
from cv_validator.structural.config import StructuralAuditConfig
from cv_validator.structural.domain import StructuralAuditResult


def audit_document(
    document: RedactedDocument,
    *,
    snapshot_month: str | None = None,
    config: StructuralAuditConfig | None = None,
) -> StructuralAuditResult:
    from cv_validator.document_understanding.annotations import (
        build_shared_annotations,
        project_structural_v1,
    )
    snapshot, _exclusion, _sections, timeline, visibility = build_shared_annotations(
        document, snapshot_month=snapshot_month, config=config
    )
    return project_structural_v1(document, snapshot, timeline, visibility)
