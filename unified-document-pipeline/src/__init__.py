"""Unified Document Pipeline — L2 reference implementation."""
from .pipeline import (
    Archiver, AuditTrail, DocumentPipeline, Extractor, Ingestor,
    Normalizer, PipelineResult, StageResult,
)
from .template import DEFAULT_FILTERS, TemplateRenderer

__version__ = "1.0.0"
__all__ = [
    "Archiver", "AuditTrail", "DocumentPipeline", "Extractor", "Ingestor",
    "Normalizer", "PipelineResult", "StageResult",
    "DEFAULT_FILTERS", "TemplateRenderer",
]
