"""Step 5 planner: conflict detection, resolution, and time-phased sequencing."""

from src.planner.conflicts import Conflict, detect_conflicts
from src.planner.resolution_rules import (
    REGISTRY,
    Resolution,
    ResolutionResult,
    Rule,
    UNRESOLVED,
    resolve_conflicts,
)
from src.planner.sequencer import (
    OptimizationPlan,
    Phase,
    PlannerError,
    build_sequence,
)

__all__ = [
    "Conflict",
    "detect_conflicts",
    "Rule",
    "Resolution",
    "ResolutionResult",
    "REGISTRY",
    "UNRESOLVED",
    "resolve_conflicts",
    "OptimizationPlan",
    "Phase",
    "PlannerError",
    "build_sequence",
]
