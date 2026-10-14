"""Compatibility imports for historical B01/B02 callers.

The shared frozen-question observation service lives in
``workbench_observation_service``. Existing imports remain stable for old
scripts, tests and case-analysis readers.
"""

from app.services.workbench_observation_service import PlanExpand, TopicAnswer, TopicService

__all__ = ["PlanExpand", "TopicAnswer", "TopicService"]
