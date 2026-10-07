"""Auditable copy-trading experiments with a paper-only execution boundary."""
from .engine import PaperConfig, PaperEngine, validate_feed

__all__ = ["PaperConfig", "PaperEngine", "validate_feed"]
