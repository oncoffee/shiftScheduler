"""Type definitions for the compliance module."""

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum
from typing import Any, Optional


class ViolationType(str, Enum):
    """Types of compliance violations."""
    MINOR_CURFEW = "MINOR_CURFEW"
    MINOR_EARLY_START = "MINOR_EARLY_START"
    MINOR_DAILY_HOURS = "MINOR_DAILY_HOURS"
    MINOR_WEEKLY_HOURS = "MINOR_WEEKLY_HOURS"
    REST_VIOLATION = "REST_VIOLATION"
    DAILY_OVERTIME = "DAILY_OVERTIME"
    WEEKLY_OVERTIME = "WEEKLY_OVERTIME"
    MEAL_BREAK_REQUIRED = "MEAL_BREAK_REQUIRED"
    REST_BREAK_REQUIRED = "REST_BREAK_REQUIRED"
    PREDICTIVE_NOTICE = "PREDICTIVE_NOTICE"


class ViolationSeverity(str, Enum):
    """Severity levels for violations."""
    ERROR = "error"  # Blocks scheduling in enforce mode
    WARNING = "warning"  # Flags but allows scheduling


@dataclass
class Violation:
    """A single compliance violation."""
    rule_type: ViolationType
    severity: ViolationSeverity
    employee_name: str
    date: Optional[str] = None  # ISO date string
    message: str = ""
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "rule_type": self.rule_type.value,
            "severity": self.severity.value,
            "employee_name": self.employee_name,
            "date": self.date,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class EmployeeCompliance:
    """Compliance-related employee information."""
    name: str
    date_of_birth: Optional[date] = None
    is_minor: bool = False
    hourly_rate: float = 0.0

    @property
    def age(self) -> Optional[int]:
        """Calculate age from date of birth."""
        if not self.date_of_birth:
            return None
        today = date.today()
        age = today.year - self.date_of_birth.year
        if (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day):
            age -= 1
        return age


@dataclass
class ShiftInfo:
    """Information about a scheduled shift."""
    employee_name: str
    date: str  # ISO date string
    day_of_week: str
    start_time: str  # HH:MM format
    end_time: str  # HH:MM format
    total_hours: float
    periods: list[int] = field(default_factory=list)  # Period indices

    @property
    def start_datetime(self) -> datetime:
        """Get start as datetime."""
        dt = datetime.fromisoformat(self.date)
        t = datetime.strptime(self.start_time, "%H:%M").time()
        return datetime.combine(dt.date(), t)

    @property
    def end_datetime(self) -> datetime:
        """Get end as datetime."""
        dt = datetime.fromisoformat(self.date)
        t = datetime.strptime(self.end_time, "%H:%M").time()
        return datetime.combine(dt.date(), t)


@dataclass
class ComplianceRules:
    """Active compliance rules for a jurisdiction."""
    jurisdiction: str = "DEFAULT"

    # Rest between shifts
    min_rest_hours: float = 8.0

    # Minor restrictions
    minor_max_daily_hours: float = 8.0
    minor_max_weekly_hours: float = 40.0
    minor_curfew_end: str = "22:00"
    minor_earliest_start: str = "06:00"
    minor_age_threshold: int = 18

    # Overtime
    daily_overtime_threshold: Optional[float] = None
    weekly_overtime_threshold: float = 40.0

    # Breaks
    meal_break_after_hours: float = 5.0
    meal_break_duration_minutes: int = 30
    rest_break_interval_hours: float = 4.0
    rest_break_duration_minutes: int = 10

    # Predictive scheduling
    advance_notice_days: int = 14

    @classmethod
    def from_doc(cls, doc) -> "ComplianceRules":
        """Create from a ComplianceRuleDoc."""
        return cls(
            jurisdiction=doc.jurisdiction,
            min_rest_hours=doc.min_rest_hours,
            minor_max_daily_hours=doc.minor_max_daily_hours,
            minor_max_weekly_hours=doc.minor_max_weekly_hours,
            minor_curfew_end=doc.minor_curfew_end,
            minor_earliest_start=doc.minor_earliest_start,
            minor_age_threshold=doc.minor_age_threshold,
            daily_overtime_threshold=doc.daily_overtime_threshold,
            weekly_overtime_threshold=doc.weekly_overtime_threshold,
            meal_break_after_hours=doc.meal_break_after_hours,
            meal_break_duration_minutes=doc.meal_break_duration_minutes,
            rest_break_interval_hours=doc.rest_break_interval_hours,
            rest_break_duration_minutes=doc.rest_break_duration_minutes,
            advance_notice_days=doc.advance_notice_days,
        )


@dataclass
class ComplianceContext:
    """Context for running compliance validation."""
    rules: ComplianceRules
    employees: dict[str, EmployeeCompliance]  # name -> info
    shifts: list[ShiftInfo]  # All shifts to validate
    previous_day_shifts: list[ShiftInfo] = field(default_factory=list)  # For rest validation
    schedule_start_date: Optional[date] = None
    published_at: Optional[datetime] = None  # When schedule was/will be published

    # Config toggles
    enable_rest_between_shifts: bool = True
    enable_minor_restrictions: bool = True
    enable_overtime_tracking: bool = True
    enable_break_compliance: bool = True
    enable_predictive_scheduling: bool = True
    compliance_mode: str = "warn"  # "off", "warn", "enforce"


@dataclass
class ComplianceResult:
    """Result of compliance validation."""
    violations: list[Violation] = field(default_factory=list)
    is_compliant: bool = True
    employee_weekly_hours: dict[str, float] = field(default_factory=dict)
    overtime_hours: dict[str, float] = field(default_factory=dict)

    def add_violation(self, violation: Violation):
        """Add a violation to the result."""
        self.violations.append(violation)
        if violation.severity == ViolationSeverity.ERROR:
            self.is_compliant = False

    @property
    def error_count(self) -> int:
        """Count of error-level violations."""
        return sum(1 for v in self.violations if v.severity == ViolationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        """Count of warning-level violations."""
        return sum(1 for v in self.violations if v.severity == ViolationSeverity.WARNING)

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "violations": [v.to_dict() for v in self.violations],
            "is_compliant": self.is_compliant,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "employee_weekly_hours": self.employee_weekly_hours,
            "overtime_hours": self.overtime_hours,
        }
