"""Shared annotations and the Structural Audit V1 compatibility projection."""
from __future__ import annotations

from cv_validator.ingestion import RedactedDocument
from cv_validator.structural.config import StructuralAuditConfig
from cv_validator.structural.domain import StructuralAuditResult


def annotate_structural_surfaces(document: RedactedDocument, snapshot_month: str, config: StructuralAuditConfig | None = None):
    # The grammar remains byte-compatible while its only production owner moves
    # behind document understanding. These private helpers are retired after V1.
    from cv_validator.structural.audit import _timeline, _visibility
    cfg = config or StructuralAuditConfig()
    return _timeline(document, snapshot_month, cfg), _visibility(document, cfg)


def project_structural_v1(document: RedactedDocument, snapshot_month: str, timeline, visibility) -> StructuralAuditResult:
    from cv_validator.structural.audit import project_structural_v1 as project
    return project(document, snapshot_month, timeline, visibility)
