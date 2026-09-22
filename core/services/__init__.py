"""Compatibility namespace for application services."""

from core.application.audit_service import AuditService
from core.application.diff_service import DiffService
from core.application.drafting_service import DraftingService

__all__ = ["AuditService", "DiffService", "DraftingService"]
from .governance import GovernanceService
from .ingestion import chunk_text, ingest_file, ingest_pdf
from .transparency import export_report, transparency_report

__all__ = ["GovernanceService", "chunk_text", "ingest_file", "ingest_pdf",
           "transparency_report", "export_report"]
