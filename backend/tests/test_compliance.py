"""Unit tests for compliance validators.

Tests minor curfew restrictions, rest between shifts, overtime detection,
meal break requirements, and rest break requirements.
"""

import pytest
from datetime import date, datetime, timedelta

from compliance.types import (
    ComplianceContext,
    ComplianceResult,
    ComplianceRules,
    EmployeeCompliance,
    ShiftInfo,
    Violation,
    ViolationType,
    ViolationSeverity,
)
from compliance.validators import (
    MinorRestrictionsValidator,
    RestBetweenShiftsValidator,
    OvertimeValidator,
    BreakComplianceValidator,
    PredictiveSchedulingValidator,
)
from compliance.engine import (
    ComplianceEngine,
    apply_minor_availability_filter,
    apply_rest_constraints,
)


# ============================================================================
# ============================================================================


@pytest.fixture
def default_rules():
    """Default compliance rules."""
    return ComplianceRules(
        jurisdiction="DEFAULT",
        min_rest_hours=8.0,
        minor_max_daily_hours=8.0,
        minor_max_weekly_hours=40.0,
        minor_curfew_end="22:00",
        minor_earliest_start="06:00",
        minor_age_threshold=18,
        daily_overtime_threshold=None,
        weekly_overtime_threshold=40.0,
        meal_break_after_hours=5.0,
        meal_break_duration_minutes=30,
        rest_break_interval_hours=4.0,
        rest_break_duration_minutes=10,
        advance_notice_days=14,
    )


@pytest.fixture
def california_rules():
    """California-specific compliance rules with daily overtime."""
    return ComplianceRules(
        jurisdiction="CA",
        min_rest_hours=10.0,
        minor_max_daily_hours=8.0,
        minor_max_weekly_hours=40.0,
        minor_curfew_end="22:00",
        minor_earliest_start="06:00",
        minor_age_threshold=18,
        daily_overtime_threshold=8.0,
        weekly_overtime_threshold=40.0,
        meal_break_after_hours=5.0,
        meal_break_duration_minutes=30,
        rest_break_interval_hours=4.0,
        rest_break_duration_minutes=10,
        advance_notice_days=14,
    )


@pytest.fixture
def adult_employee():
    """Adult employee (over 18)."""
    return EmployeeCompliance(
        name="Alice",
        date_of_birth=date(1990, 5, 15),
        is_minor=False,
        hourly_rate=15.0,
    )


@pytest.fixture
def minor_employee():
    """Minor employee (under 18)."""
  
    today = date.today()
    dob = date(today.year - 17, today.month, today.day)
    return EmployeeCompliance(
        name="Bobby",
        date_of_birth=dob,
        is_minor=True,
        hourly_rate=12.0,
    )


@pytest.fixture
def make_shift():
    """Factory to create ShiftInfo objects."""
    def _make_shift(
        employee: str,
        date_str: str,
        start_time: str,
        end_time: str,
        total_hours: float,
        day_of_week: str = "Monday",
        periods: list[int] = None,
    ) -> ShiftInfo:
        return ShiftInfo(
            employee_name=employee,
            date=date_str,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            total_hours=total_hours,
            periods=periods or [],
        )
    return _make_shift


@pytest.fixture
def make_context(default_rules):
    """Factory to create ComplianceContext objects."""
    def _make_context(
        employees: dict[str, EmployeeCompliance],
        shifts: list[ShiftInfo],
        previous_shifts: list[ShiftInfo] = None,
        rules: ComplianceRules = None,
        compliance_mode: str = "warn",
        schedule_start_date: date = None,
        published_at: datetime = None,
        **kwargs
    ) -> ComplianceContext:
        return ComplianceContext(
            rules=rules or default_rules,
            employees=employees,
            shifts=shifts,
            previous_day_shifts=previous_shifts or [],
            schedule_start_date=schedule_start_date,
            published_at=published_at,
            compliance_mode=compliance_mode,
            **kwargs
        )
    return _make_context


# ============================================================================
# ============================================================================


class TestMinorRestrictionsValidator:
    """Test minor employee restrictions validation."""

    def test_no_violations_for_adult_late_shift(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        """Adults working late should not trigger curfew violations."""
        shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="16:00",
            end_time="23:00",
            total_hours=7.0,
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[shift],
        )

        result = ComplianceResult()
        validator = MinorRestrictionsValidator()
        validator.validate(context, result)

      
        curfew_violations = [v for v in result.violations if v.rule_type == ViolationType.MINOR_CURFEW]
        assert len(curfew_violations) == 0

    def test_curfew_violation_for_minor(
        self, default_rules, minor_employee, make_shift, make_context
    ):
        """Minors working past curfew should trigger violation."""
        shift = make_shift(
            employee="Bobby",
            date_str="2024-01-15",
            start_time="18:00",
            end_time="23:00",
            total_hours=5.0,
        )

        context = make_context(
            employees={"Bobby": minor_employee},
            shifts=[shift],
        )

        result = ComplianceResult()
        validator = MinorRestrictionsValidator()
        validator.validate(context, result)

        curfew_violations = [v for v in result.violations if v.rule_type == ViolationType.MINOR_CURFEW]
        assert len(curfew_violations) == 1
        assert curfew_violations[0].employee_name == "Bobby"

    def test_no_curfew_violation_when_ending_at_curfew(
        self, default_rules, minor_employee, make_shift, make_context
    ):
        """Minors ending exactly at curfew should not trigger violation."""
        shift = make_shift(
            employee="Bobby",
            date_str="2024-01-15",
            start_time="17:00",
            end_time="22:00",
            total_hours=5.0,
        )

        context = make_context(
            employees={"Bobby": minor_employee},
            shifts=[shift],
        )

        result = ComplianceResult()
        validator = MinorRestrictionsValidator()
        validator.validate(context, result)

        curfew_violations = [v for v in result.violations if v.rule_type == ViolationType.MINOR_CURFEW]
        assert len(curfew_violations) == 0

    def test_early_start_violation_for_minor(
        self, default_rules, minor_employee, make_shift, make_context
    ):
        """Minors starting before allowed time should trigger violation."""
        shift = make_shift(
            employee="Bobby",
            date_str="2024-01-15",
            start_time="05:00",
            end_time="10:00",
            total_hours=5.0,
        )

        context = make_context(
            employees={"Bobby": minor_employee},
            shifts=[shift],
        )

        result = ComplianceResult()
        validator = MinorRestrictionsValidator()
        validator.validate(context, result)

        early_violations = [v for v in result.violations if v.rule_type == ViolationType.MINOR_EARLY_START]
        assert len(early_violations) == 1
        assert early_violations[0].employee_name == "Bobby"

    def test_minor_daily_hours_violation(
        self, default_rules, minor_employee, make_shift, make_context
    ):
        """Minors working more than max daily hours should trigger violation."""
        shift = make_shift(
            employee="Bobby",
            date_str="2024-01-15",
            start_time="08:00",
            end_time="18:00",
            total_hours=10.0,
        )

        context = make_context(
            employees={"Bobby": minor_employee},
            shifts=[shift],
        )

        result = ComplianceResult()
        validator = MinorRestrictionsValidator()
        validator.validate(context, result)

        daily_hour_violations = [v for v in result.violations if v.rule_type == ViolationType.MINOR_DAILY_HOURS]
        assert len(daily_hour_violations) == 1

    def test_minor_weekly_hours_violation(
        self, default_rules, minor_employee, make_shift, make_context
    ):
        """Minors working more than max weekly hours should trigger violation."""
      
        shifts = []
        for i, day in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]):
            shifts.append(make_shift(
                employee="Bobby",
                date_str=f"2024-01-{15 + i}",
                start_time="09:00",
                end_time="17:00",
                total_hours=8.0,
                day_of_week=day,
            ))

        context = make_context(
            employees={"Bobby": minor_employee},
            shifts=shifts,
        )

        result = ComplianceResult()
        validator = MinorRestrictionsValidator()
        validator.validate(context, result)

        weekly_violations = [v for v in result.violations if v.rule_type == ViolationType.MINOR_WEEKLY_HOURS]
        assert len(weekly_violations) == 1

    def test_minor_restrictions_disabled(
        self, default_rules, minor_employee, make_shift, make_context
    ):
        """No violations when minor restrictions are disabled."""
        shift = make_shift(
            employee="Bobby",
            date_str="2024-01-15",
            start_time="18:00",
            end_time="23:00",
            total_hours=5.0,
        )

        context = make_context(
            employees={"Bobby": minor_employee},
            shifts=[shift],
            enable_minor_restrictions=False,
        )

        result = ComplianceResult()
        validator = MinorRestrictionsValidator()
        validator.validate(context, result)

        assert len(result.violations) == 0

    def test_enforce_mode_creates_error_violations(
        self, default_rules, minor_employee, make_shift, make_context
    ):
        """In enforce mode, violations should be errors not warnings."""
        shift = make_shift(
            employee="Bobby",
            date_str="2024-01-15",
            start_time="18:00",
            end_time="23:00",
            total_hours=5.0,
        )

        context = make_context(
            employees={"Bobby": minor_employee},
            shifts=[shift],
            compliance_mode="enforce",
        )

        result = ComplianceResult()
        validator = MinorRestrictionsValidator()
        validator.validate(context, result)

        assert len(result.violations) > 0
        for v in result.violations:
            assert v.severity == ViolationSeverity.ERROR
        assert result.is_compliant is False


# ============================================================================
# ============================================================================


class TestRestBetweenShiftsValidator:
    """Test rest between shifts (anti-clopening) validation."""

    def test_no_violation_with_adequate_rest(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        """No violation when there's enough rest between shifts."""
        previous_shift = make_shift(
            employee="Alice",
            date_str="2024-01-14",
            start_time="09:00",
            end_time="14:00",
            total_hours=5.0,
            day_of_week="Sunday",
        )

        current_shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="09:00",
            end_time="14:00",
            total_hours=5.0,
            day_of_week="Monday",
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[current_shift],
            previous_shifts=[previous_shift],
        )

        result = ComplianceResult()
        validator = RestBetweenShiftsValidator()
        validator.validate(context, result)

        rest_violations = [v for v in result.violations if v.rule_type == ViolationType.REST_VIOLATION]
        assert len(rest_violations) == 0

    def test_violation_with_insufficient_rest(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        """Violation when rest between shifts is too short."""
        previous_shift = make_shift(
            employee="Alice",
            date_str="2024-01-14",
            start_time="18:00",
            end_time="22:00",
            total_hours=4.0,
            day_of_week="Sunday",
        )

        current_shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="05:00",
            end_time="12:00",
            total_hours=7.0,
            day_of_week="Monday",
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[current_shift],
            previous_shifts=[previous_shift],
        )

        result = ComplianceResult()
        validator = RestBetweenShiftsValidator()
        validator.validate(context, result)

        rest_violations = [v for v in result.violations if v.rule_type == ViolationType.REST_VIOLATION]
        assert len(rest_violations) == 1
        assert rest_violations[0].employee_name == "Alice"

    def test_clopening_scenario(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        """Classic clopening: close late, open early."""
        previous_shift = make_shift(
            employee="Alice",
            date_str="2024-01-14",
            start_time="16:00",
            end_time="23:00",
            total_hours=7.0,
            day_of_week="Sunday",
        )

        current_shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="06:00",
            end_time="14:00",
            total_hours=8.0,
            day_of_week="Monday",
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[current_shift],
            previous_shifts=[previous_shift],
        )

        result = ComplianceResult()
        validator = RestBetweenShiftsValidator()
        validator.validate(context, result)

        rest_violations = [v for v in result.violations if v.rule_type == ViolationType.REST_VIOLATION]
        assert len(rest_violations) == 1

    def test_rest_validation_disabled(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        """No violations when rest validation is disabled."""
        previous_shift = make_shift(
            employee="Alice",
            date_str="2024-01-14",
            start_time="18:00",
            end_time="22:00",
            total_hours=4.0,
            day_of_week="Sunday",
        )

        current_shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="05:00",
            end_time="12:00",
            total_hours=7.0,
            day_of_week="Monday",
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[current_shift],
            previous_shifts=[previous_shift],
            enable_rest_between_shifts=False,
        )

        result = ComplianceResult()
        validator = RestBetweenShiftsValidator()
        validator.validate(context, result)

        assert len(result.violations) == 0


# ============================================================================
# ============================================================================


class TestOvertimeValidator:
    """Test overtime detection validation."""

    def test_no_weekly_overtime_under_threshold(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        """No weekly OT violation when under 40 hours."""
        shifts = []
        for i, day in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]):
            shifts.append(make_shift(
                employee="Alice",
                date_str=f"2024-01-{15 + i}",
                start_time="09:00",
                end_time="17:00",
                total_hours=8.0,
                day_of_week=day,
            ))

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=shifts,
        )

        result = ComplianceResult()
        validator = OvertimeValidator()
        validator.validate(context, result)

        weekly_ot = [v for v in result.violations if v.rule_type == ViolationType.WEEKLY_OVERTIME]
        assert len(weekly_ot) == 0
        assert result.employee_weekly_hours.get("Alice") == 40.0

    def test_weekly_overtime_over_threshold(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        """Weekly OT violation when over 40 hours."""
        shifts = []
        for i, day in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]):
            shifts.append(make_shift(
                employee="Alice",
                date_str=f"2024-01-{15 + i}",
                start_time="09:00",
                end_time="17:00",
                total_hours=8.0,
                day_of_week=day,
            ))

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=shifts,
        )

        result = ComplianceResult()
        validator = OvertimeValidator()
        validator.validate(context, result)

        weekly_ot = [v for v in result.violations if v.rule_type == ViolationType.WEEKLY_OVERTIME]
        assert len(weekly_ot) == 1
        assert result.employee_weekly_hours.get("Alice") == 48.0
        assert result.overtime_hours.get("Alice") == 8.0

    def test_daily_overtime_with_california_rules(
        self, california_rules, adult_employee, make_shift, make_context
    ):
        """Daily OT violation with California rules (> 8 hours)."""
        shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="08:00",
            end_time="19:00",
            total_hours=11.0,
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[shift],
            rules=california_rules,
        )

        result = ComplianceResult()
        validator = OvertimeValidator()
        validator.validate(context, result)

        daily_ot = [v for v in result.violations if v.rule_type == ViolationType.DAILY_OVERTIME]
        assert len(daily_ot) == 1
        assert daily_ot[0].details["overtime_hours"] == 3.0

    def test_no_daily_overtime_without_threshold(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        """No daily OT when threshold is not set."""
        shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="08:00",
            end_time="19:00",
            total_hours=11.0,
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[shift],
        )

        result = ComplianceResult()
        validator = OvertimeValidator()
        validator.validate(context, result)

        daily_ot = [v for v in result.violations if v.rule_type == ViolationType.DAILY_OVERTIME]
        assert len(daily_ot) == 0

    def test_overtime_tracking_disabled(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        """No violations when overtime tracking is disabled."""
        shifts = []
        for i in range(6):
            shifts.append(make_shift(
                employee="Alice",
                date_str=f"2024-01-{15 + i}",
                start_time="09:00",
                end_time="17:00",
                total_hours=8.0,
            ))

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=shifts,
            enable_overtime_tracking=False,
        )

        result = ComplianceResult()
        validator = OvertimeValidator()
        validator.validate(context, result)

        assert len(result.violations) == 0


# ============================================================================
# ============================================================================


class TestBreakComplianceValidator:
    """Test meal and rest break requirements validation."""

    def test_meal_break_required_for_long_shift(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        """Meal break required for shifts > 5 hours."""
        shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="09:00",
            end_time="15:00",
            total_hours=6.0,
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[shift],
        )

        result = ComplianceResult()
        validator = BreakComplianceValidator()
        validator.validate(context, result)

        meal_violations = [v for v in result.violations if v.rule_type == ViolationType.MEAL_BREAK_REQUIRED]
        assert len(meal_violations) == 1
        assert meal_violations[0].details["break_duration"] == 30

    def test_no_meal_break_for_short_shift(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        """No meal break required for shifts <= 5 hours."""
        shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="09:00",
            end_time="14:00",
            total_hours=5.0,
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[shift],
        )

        result = ComplianceResult()
        validator = BreakComplianceValidator()
        validator.validate(context, result)

        meal_violations = [v for v in result.violations if v.rule_type == ViolationType.MEAL_BREAK_REQUIRED]
        assert len(meal_violations) == 0

    def test_rest_break_required_for_4_hour_shift(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        """Rest break required for shifts >= 4 hours."""
        shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="09:00",
            end_time="13:00",
            total_hours=4.0,
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[shift],
        )

        result = ComplianceResult()
        validator = BreakComplianceValidator()
        validator.validate(context, result)

        rest_violations = [v for v in result.violations if v.rule_type == ViolationType.REST_BREAK_REQUIRED]
        assert len(rest_violations) == 1

    def test_multiple_rest_breaks_for_long_shift(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        """Multiple rest breaks for very long shifts."""
        shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="08:00",
            end_time="18:00",
            total_hours=10.0,
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[shift],
        )

        result = ComplianceResult()
        validator = BreakComplianceValidator()
        validator.validate(context, result)

        rest_violations = [v for v in result.violations if v.rule_type == ViolationType.REST_BREAK_REQUIRED]
        assert len(rest_violations) == 1
      
        assert rest_violations[0].details["breaks_needed"] == 2

    def test_break_compliance_disabled(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        """No violations when break compliance is disabled."""
        shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="09:00",
            end_time="17:00",
            total_hours=8.0,
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[shift],
            enable_break_compliance=False,
        )

        result = ComplianceResult()
        validator = BreakComplianceValidator()
        validator.validate(context, result)

        assert len(result.violations) == 0

    def test_zero_hour_shift_no_breaks(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        """Zero hour shifts should not trigger break requirements."""
        shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="09:00",
            end_time="09:00",
            total_hours=0.0,
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[shift],
        )

        result = ComplianceResult()
        validator = BreakComplianceValidator()
        validator.validate(context, result)

        assert len(result.violations) == 0


# ============================================================================
# ============================================================================


class TestPredictiveSchedulingValidator:
    """Test predictive scheduling (advance notice) validation."""

    def test_no_violation_with_adequate_notice(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        """No violation when schedule published with adequate notice."""
        schedule_start = date(2024, 2, 1)
        published_at = datetime(2024, 1, 15, 10, 0)

        shift = make_shift(
            employee="Alice",
            date_str="2024-02-01",
            start_time="09:00",
            end_time="17:00",
            total_hours=8.0,
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[shift],
            schedule_start_date=schedule_start,
            published_at=published_at,
        )

        result = ComplianceResult()
        validator = PredictiveSchedulingValidator()
        validator.validate(context, result)

        notice_violations = [v for v in result.violations if v.rule_type == ViolationType.PREDICTIVE_NOTICE]
        assert len(notice_violations) == 0

    def test_violation_with_insufficient_notice(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        """Violation when schedule published without adequate notice."""
        schedule_start = date(2024, 2, 1)
        published_at = datetime(2024, 1, 25, 10, 0)

        shift = make_shift(
            employee="Alice",
            date_str="2024-02-01",
            start_time="09:00",
            end_time="17:00",
            total_hours=8.0,
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[shift],
            schedule_start_date=schedule_start,
            published_at=published_at,
        )

        result = ComplianceResult()
        validator = PredictiveSchedulingValidator()
        validator.validate(context, result)

        notice_violations = [v for v in result.violations if v.rule_type == ViolationType.PREDICTIVE_NOTICE]
        assert len(notice_violations) == 1
        assert notice_violations[0].details["actual_notice_days"] == 7

    def test_predictive_scheduling_disabled(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        """No violations when predictive scheduling is disabled."""
        schedule_start = date(2024, 2, 1)
        published_at = datetime(2024, 1, 31, 10, 0)

        shift = make_shift(
            employee="Alice",
            date_str="2024-02-01",
            start_time="09:00",
            end_time="17:00",
            total_hours=8.0,
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[shift],
            schedule_start_date=schedule_start,
            published_at=published_at,
            enable_predictive_scheduling=False,
        )

        result = ComplianceResult()
        validator = PredictiveSchedulingValidator()
        validator.validate(context, result)

        assert len(result.violations) == 0


# ============================================================================
# ============================================================================


class TestComplianceEngine:
    """Test the compliance engine orchestration."""

    def test_engine_runs_all_validators(
        self, default_rules, minor_employee, adult_employee, make_shift
    ):
        """Engine should run all validators and aggregate results."""
      
        minor_shift = make_shift(
            employee="Bobby",
            date_str="2024-01-15",
            start_time="18:00",
            end_time="23:00",
            total_hours=5.0,
        )

        long_shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="08:00",
            end_time="16:00",
            total_hours=8.0,
        )

        context = ComplianceContext(
            rules=default_rules,
            employees={
                "Bobby": minor_employee,
                "Alice": adult_employee,
            },
            shifts=[minor_shift, long_shift],
            compliance_mode="warn",
        )

        engine = ComplianceEngine()
        result = engine.validate(context)

      
        violation_types = [v.rule_type for v in result.violations]
        assert ViolationType.MINOR_CURFEW in violation_types
        assert ViolationType.MEAL_BREAK_REQUIRED in violation_types

    def test_engine_respects_off_mode(self, default_rules, minor_employee, make_shift):
        """Engine should skip validation in off mode."""
        shift = make_shift(
            employee="Bobby",
            date_str="2024-01-15",
            start_time="18:00",
            end_time="23:00",
            total_hours=5.0,
        )

        context = ComplianceContext(
            rules=default_rules,
            employees={"Bobby": minor_employee},
            shifts=[shift],
            compliance_mode="off",
        )

        engine = ComplianceEngine()
        result = engine.validate(context)

        assert len(result.violations) == 0

    def test_build_context_from_raw_data(self, default_rules):
        """Test building context from raw API data."""
        employees = [
            {
                "employee_name": "Alice",
                "date_of_birth": "1990-05-15",
                "is_minor": False,
                "hourly_rate": 15.0,
            }
        ]

        assignments = [
            {
                "employee_name": "Alice",
                "date": "2024-01-15",
                "day_of_week": "Monday",
                "shift_start": "09:00",
                "shift_end": "17:00",
                "total_hours": 8.0,
                "periods": [
                    {"period_index": 0, "scheduled": True},
                    {"period_index": 1, "scheduled": True},
                ],
            }
        ]

        context = ComplianceEngine.build_context(
            rules=default_rules,
            employees=employees,
            assignments=assignments,
            config={"compliance_mode": "warn"},
        )

        assert len(context.employees) == 1
        assert len(context.shifts) == 1
        assert context.shifts[0].total_hours == 8.0


# ============================================================================
# ============================================================================


class TestApplyMinorAvailabilityFilter:
    """Test the minor availability filter function."""

    def test_filters_curfew_periods_for_minors(self):
        """Minor availability should be filtered for curfew."""
        time_periods = [
            "18:00", "18:30", "19:00", "19:30", "20:00", "20:30",
            "21:00", "21:30", "22:00", "22:30", "23:00"
        ]

      
        availability = {
            "Bobby": list(range(11)),
            "Alice": list(range(11)),
        }

        is_minor = {
            "Bobby": True,
            "Alice": False,
        }

        filtered, curfew_idx, earliest_idx = apply_minor_availability_filter(
            availability,
            is_minor,
            time_periods,
            curfew_time="22:00",
            earliest_time="06:00",
        )

      
      
      
        assert len(filtered["Bobby"]) <= 8
        assert all(idx < 8 for idx in filtered["Bobby"])

      
        assert filtered["Alice"] == list(range(11))

    def test_filters_early_periods_for_minors(self):
        """Minor availability should be filtered for early start."""
        time_periods = [
            "05:00", "05:30", "06:00", "06:30", "07:00", "07:30"
        ]

      
        availability = {
            "Bobby": list(range(6)),
            "Alice": list(range(6)),
        }

        is_minor = {
            "Bobby": True,
            "Alice": False,
        }

        filtered, curfew_idx, earliest_idx = apply_minor_availability_filter(
            availability,
            is_minor,
            time_periods,
            curfew_time="22:00",
            earliest_time="06:00",
        )

      
      
      
        assert len(filtered["Bobby"]) <= 4
        assert all(idx >= 2 for idx in filtered["Bobby"])


class TestApplyRestConstraints:
    """Test the rest constraint application function."""

    def test_blocks_periods_after_late_shift(self):
        """Should block early periods after a late shift."""
        time_periods = [
            "06:00", "06:30", "07:00", "07:30", "08:00", "08:30",
            "09:00", "09:30", "10:00"
        ]

        previous_end_times = {
            "Alice": "23:00",
        }

        availability = {
            "Alice": [1] * 9,
        }

        blocked = apply_rest_constraints(
            availability,
            previous_end_times,
            time_periods,
            min_rest_hours=10.0,
        )

      
      
        assert "Alice" in blocked
        assert 0 in blocked["Alice"]
        assert 1 in blocked["Alice"]
        assert 2 in blocked["Alice"]

    def test_no_blocking_with_adequate_rest(self):
        """Should not block periods with adequate rest."""
        time_periods = [
            "09:00", "09:30", "10:00", "10:30"
        ]

        previous_end_times = {
            "Alice": "18:00",
        }

        availability = {
            "Alice": [1] * 4,
        }

        blocked = apply_rest_constraints(
            availability,
            previous_end_times,
            time_periods,
            min_rest_hours=8.0,
        )

      
      
        alice_blocked = blocked.get("Alice", set())
        assert len(alice_blocked) == 0


# ============================================================================
# ============================================================================


class TestComplianceResult:
    """Test ComplianceResult functionality."""

    def test_add_error_violation_marks_non_compliant(self):
        """Adding error violation should mark result as non-compliant."""
        result = ComplianceResult()
        assert result.is_compliant is True

        result.add_violation(Violation(
            rule_type=ViolationType.MINOR_CURFEW,
            severity=ViolationSeverity.ERROR,
            employee_name="Bobby",
            message="Test",
        ))

        assert result.is_compliant is False
        assert result.error_count == 1

    def test_add_warning_violation_stays_compliant(self):
        """Adding warning violation should keep result compliant."""
        result = ComplianceResult()

        result.add_violation(Violation(
            rule_type=ViolationType.WEEKLY_OVERTIME,
            severity=ViolationSeverity.WARNING,
            employee_name="Alice",
            message="Test",
        ))

        assert result.is_compliant is True
        assert result.warning_count == 1

    def test_to_dict_format(self):
        """Test the to_dict output format."""
        result = ComplianceResult()
        result.add_violation(Violation(
            rule_type=ViolationType.MINOR_CURFEW,
            severity=ViolationSeverity.WARNING,
            employee_name="Bobby",
            date="2024-01-15",
            message="Curfew violation",
            details={"curfew": "22:00"},
        ))
        result.employee_weekly_hours["Alice"] = 40.0

        output = result.to_dict()

        assert "violations" in output
        assert "is_compliant" in output
        assert "error_count" in output
        assert "warning_count" in output
        assert "employee_weekly_hours" in output
        assert output["employee_weekly_hours"]["Alice"] == 40.0
