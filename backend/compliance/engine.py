"""Compliance validation engine that orchestrates all validators."""

from datetime import date, datetime
from typing import Optional

from .types import (
    ComplianceContext,
    ComplianceResult,
    ComplianceRules,
    EmployeeCompliance,
    ShiftInfo,
)
from .validators import (
    BaseValidator,
    MinorRestrictionsValidator,
    RestBetweenShiftsValidator,
    OvertimeValidator,
    BreakComplianceValidator,
    PredictiveSchedulingValidator,
)


class ComplianceEngine:
    """
    Main engine for running compliance validation.

    Orchestrates all validators and generates a compliance report.
    """

    def __init__(self):
        """Initialize with all validators."""
        self.validators: list[BaseValidator] = [
            MinorRestrictionsValidator(),
            RestBetweenShiftsValidator(),
            OvertimeValidator(),
            BreakComplianceValidator(),
            PredictiveSchedulingValidator(),
        ]

    def validate(self, context: ComplianceContext) -> ComplianceResult:
        """
        Run all compliance validations.

        Args:
            context: The compliance context with rules, employees, and shifts

        Returns:
            ComplianceResult with all violations found
        """
        if context.compliance_mode == "off":
            return ComplianceResult()

        result = ComplianceResult()

        for validator in self.validators:
            validator.validate(context, result)

        return result

    @classmethod
    def build_context(
        cls,
        rules: ComplianceRules,
        employees: list[dict],
        assignments: list[dict],
        previous_assignments: Optional[list[dict]] = None,
        schedule_start_date: Optional[date] = None,
        published_at: Optional[datetime] = None,
        config: Optional[dict] = None,
    ) -> ComplianceContext:
        """
        Build a ComplianceContext from raw data.

        Args:
            rules: Compliance rules for the jurisdiction
            employees: List of employee dicts with name, date_of_birth, is_minor
            assignments: List of assignment dicts from the schedule
            previous_assignments: Assignments from previous day (for rest validation)
            schedule_start_date: Start date of the schedule
            published_at: When the schedule was published
            config: Config dict with compliance toggles

        Returns:
            ComplianceContext ready for validation
        """
        config = config or {}

        # Build employee compliance info
        employee_map: dict[str, EmployeeCompliance] = {}
        for emp in employees:
            dob = emp.get("date_of_birth")
            if isinstance(dob, str):
                dob = date.fromisoformat(dob)

            is_minor = emp.get("is_minor", False)
            # Auto-calculate minor status from DOB if available
            if dob and not is_minor:
                today = date.today()
                age = today.year - dob.year
                if (today.month, today.day) < (dob.month, dob.day):
                    age -= 1
                is_minor = age < rules.minor_age_threshold

            employee_map[emp["employee_name"]] = EmployeeCompliance(
                name=emp["employee_name"],
                date_of_birth=dob,
                is_minor=is_minor,
                hourly_rate=emp.get("hourly_rate", 0.0),
            )

        # Build shift info from assignments
        shifts = cls._assignments_to_shifts(assignments)
        previous_shifts = cls._assignments_to_shifts(previous_assignments or [])

        return ComplianceContext(
            rules=rules,
            employees=employee_map,
            shifts=shifts,
            previous_day_shifts=previous_shifts,
            schedule_start_date=schedule_start_date,
            published_at=published_at,
            enable_rest_between_shifts=config.get("enable_rest_between_shifts", True),
            enable_minor_restrictions=config.get("enable_minor_restrictions", True),
            enable_overtime_tracking=config.get("enable_overtime_tracking", True),
            enable_break_compliance=config.get("enable_break_compliance", True),
            enable_predictive_scheduling=config.get("enable_predictive_scheduling", True),
            compliance_mode=config.get("compliance_mode", "warn"),
        )

    @staticmethod
    def _assignments_to_shifts(assignments: list[dict]) -> list[ShiftInfo]:
        """Convert assignment dicts to ShiftInfo objects."""
        shifts = []
        for assignment in assignments:
            if assignment.get("total_hours", 0) <= 0:
                continue

            shift_start = assignment.get("shift_start")
            shift_end = assignment.get("shift_end")
            if not shift_start or not shift_end:
                continue

            # Get scheduled period indices
            periods = []
            for p in assignment.get("periods", []):
                if p.get("scheduled", False):
                    periods.append(p.get("period_index", 0))

            shifts.append(ShiftInfo(
                employee_name=assignment["employee_name"],
                date=assignment.get("date", ""),
                day_of_week=assignment.get("day_of_week", ""),
                start_time=shift_start,
                end_time=shift_end,
                total_hours=assignment.get("total_hours", 0),
                periods=periods,
            ))

        return shifts


async def validate_schedule_compliance(
    schedule_run,  # ScheduleRunDoc
    employees: list,  # List of EmployeeDoc
    previous_schedule_run=None,  # Optional previous ScheduleRunDoc
) -> ComplianceResult:
    """
    Validate a schedule run for compliance.

    This is a convenience function for use in the API layer.

    Args:
        schedule_run: The schedule to validate
        employees: List of employees
        previous_schedule_run: Previous day's schedule for rest validation

    Returns:
        ComplianceResult with violations
    """
    from db import ConfigDoc, ComplianceRuleDoc

    # Get config
    config = await ConfigDoc.find_one()
    if not config or config.compliance_mode == "off":
        return ComplianceResult()

    # Get compliance rules for the store's jurisdiction
    # For now, get the store and find its jurisdiction
    from db import StoreDoc
    store = await StoreDoc.find_one(StoreDoc.store_name == schedule_run.store_name)
    jurisdiction = store.jurisdiction if store else "DEFAULT"

    rules_doc = await ComplianceRuleDoc.find_one(
        ComplianceRuleDoc.jurisdiction == jurisdiction
    )
    if not rules_doc:
        # Try DEFAULT rules
        rules_doc = await ComplianceRuleDoc.find_one(
            ComplianceRuleDoc.jurisdiction == "DEFAULT"
        )

    if rules_doc:
        rules = ComplianceRules.from_doc(rules_doc)
    else:
        rules = ComplianceRules()  # Use defaults

    # Build employee list
    emp_list = [
        {
            "employee_name": e.employee_name,
            "date_of_birth": e.date_of_birth,
            "is_minor": e.is_minor,
            "hourly_rate": e.hourly_rate,
        }
        for e in employees
    ]

    # Build assignments
    assignments = [a.model_dump() for a in schedule_run.assignments]
    previous_assignments = []
    if previous_schedule_run:
        previous_assignments = [a.model_dump() for a in previous_schedule_run.assignments]

    # Build context
    context = ComplianceEngine.build_context(
        rules=rules,
        employees=emp_list,
        assignments=assignments,
        previous_assignments=previous_assignments,
        schedule_start_date=schedule_run.start_date.date() if schedule_run.start_date else None,
        published_at=schedule_run.published_at,
        config={
            "compliance_mode": config.compliance_mode,
            "enable_rest_between_shifts": config.enable_rest_between_shifts,
            "enable_minor_restrictions": config.enable_minor_restrictions,
            "enable_overtime_tracking": config.enable_overtime_tracking,
            "enable_break_compliance": config.enable_break_compliance,
            "enable_predictive_scheduling": config.enable_predictive_scheduling,
        },
    )

    # Run validation
    engine = ComplianceEngine()
    return engine.validate(context)


def apply_minor_availability_filter(
    employee_availability: dict[str, list[int]],
    employee_is_minor: dict[str, bool],
    time_periods: list[str],
    curfew_time: str = "22:00",
    earliest_time: str = "06:00",
) -> tuple[dict[str, list[int]], int | None, int | None]:
    """
    Pre-filter availability for minors based on curfew restrictions.

    This modifies availability BEFORE the solver runs to enforce minor restrictions.

    Args:
        employee_availability: Dict of employee -> available period indices
        employee_is_minor: Dict of employee -> is_minor boolean
        time_periods: List of period time strings (e.g., ["06:00", "06:30", ...])
        curfew_time: Time after which minors cannot work (HH:MM)
        earliest_time: Time before which minors cannot work (HH:MM)

    Returns:
        Tuple of (filtered_availability, curfew_period_index, earliest_period_index)
    """
    from datetime import datetime

    curfew = datetime.strptime(curfew_time, "%H:%M").time()
    earliest = datetime.strptime(earliest_time, "%H:%M").time()

    # Find period indices for curfew and earliest
    curfew_period = None
    earliest_period = None

    for idx, period in enumerate(time_periods):
        period_time = datetime.strptime(period, "%H:%M").time()
        if curfew_period is None and period_time >= curfew:
            curfew_period = idx
        if period_time >= earliest and earliest_period is None:
            earliest_period = idx

    # Filter availability for minors
    filtered = {}
    for emp, periods in employee_availability.items():
        if employee_is_minor.get(emp, False):
            # Filter out periods outside allowed times
            filtered[emp] = [
                p for p in periods
                if (earliest_period is None or p >= earliest_period) and
                   (curfew_period is None or p < curfew_period)
            ]
        else:
            filtered[emp] = periods

    return filtered, curfew_period, earliest_period


def apply_rest_constraints(
    employee_availability: dict[str, list[int]],
    previous_day_end_times: dict[str, str],  # employee -> end time "HH:MM"
    time_periods: list[str],
    min_rest_hours: float,
    store_open_time: str = "06:00",
) -> dict[str, set[int]]:
    """
    Calculate which periods should be blocked due to rest requirements.

    If an employee ended their shift at 10pm and min rest is 10 hours,
    they cannot start until 8am the next day.

    Args:
        employee_availability: Current availability
        previous_day_end_times: When each employee ended their shift yesterday
        time_periods: List of period times
        min_rest_hours: Minimum rest hours required
        store_open_time: When the store opens

    Returns:
        Dict of employee -> set of blocked period indices
    """
    from datetime import datetime, timedelta

    blocked_periods: dict[str, set[int]] = {}

    for emp, end_time_str in previous_day_end_times.items():
        if not end_time_str:
            continue

        # Calculate earliest allowed start time
        end_time = datetime.strptime(end_time_str, "%H:%M")
        # Add min rest hours, wrapping to next day
        earliest_start = end_time + timedelta(hours=min_rest_hours)

        # If earliest start is after midnight, calculate the actual time
        earliest_start_time = earliest_start.time()

        blocked = set()
        for idx, period in enumerate(time_periods):
            period_time = datetime.strptime(period, "%H:%M").time()
            if period_time < earliest_start_time:
                blocked.add(idx)

        if blocked:
            blocked_periods[emp] = blocked

    return blocked_periods
