"""Compatibility import for existing B01/B02 callers."""
from app.services.legacy_topic_projection import project, _number, _opt

__all__ = ["project", "_number", "_opt"]
