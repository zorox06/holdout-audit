"""Evidence-first checks for tabular train/test splits. No runtime dependencies."""

from .core import AuditError, AuditFailed, Report, audit

__version__ = "0.2.0"
__all__ = ["AuditError", "AuditFailed", "Report", "audit"]
