"""Labor law compliance module for shift scheduling."""

from .types import (
    ComplianceContext,
    ComplianceResult,
    ViolationType,
    ViolationSeverity,
)
from .engine import ComplianceEngine
from .validators import (
    BaseValidator,
    MinorRestrictionsValidator,
    RestBetweenShiftsValidator,
    OvertimeValidator,
    BreakComplianceValidator,
    PredictiveSchedulingValidator,
)

__all__ = [
    "ComplianceContext",
    "ComplianceResult",
    "ViolationType",
    "ViolationSeverity",
    "ComplianceEngine",
    "BaseValidator",
    "MinorRestrictionsValidator",
    "RestBetweenShiftsValidator",
    "OvertimeValidator",
    "BreakComplianceValidator",
    "PredictiveSchedulingValidator",
]
