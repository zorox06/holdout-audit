"""Evidence-first checks for tabular train/test splits. No runtime dependencies."""

from .core import AuditError, Report, audit

__version__ = "0.1.0"
__all__ = ["AuditError", "Report", "audit"]
