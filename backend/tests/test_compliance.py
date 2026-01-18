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


@pytest.fixture
def default_rules():
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
    return EmployeeCompliance(
        name="Alice",
        date_of_birth=date(1990, 5, 15),
        is_minor=False,
        hourly_rate=15.0,
    )


@pytest.fixture
def minor_employee():
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


class TestMinorRestrictionsValidator:

    def test_no_violations_for_adult_late_shift(
        self, default_rules, adult_employee, make_shift, make_context
    ):
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


class TestRestBetweenShiftsValidator:

    def test_no_violation_with_adequate_rest(
        self, default_rules, adult_employee, make_shift, make_context
    ):
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


class TestOvertimeValidator:

    def test_no_weekly_overtime_under_threshold(
        self, default_rules, adult_employee, make_shift, make_context
    ):
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


class TestBreakComplianceValidator:

    def test_meal_break_required_for_long_shift(
        self, default_rules, adult_employee, make_shift, make_context
    ):
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


class TestPredictiveSchedulingValidator:

    def test_no_violation_with_adequate_notice(
        self, default_rules, adult_employee, make_shift, make_context
    ):
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


class TestComplianceEngine:

    def test_engine_runs_all_validators(
        self, default_rules, minor_employee, adult_employee, make_shift
    ):
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


class TestApplyMinorAvailabilityFilter:

    def test_filters_curfew_periods_for_minors(self):
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

    def test_blocks_periods_after_late_shift(self):
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


class TestComplianceResult:

    def test_add_error_violation_marks_non_compliant(self):
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


class TestMinorMultipleShiftsSameDay:

    def test_multiple_shifts_sum_hours_within_limit(
        self, default_rules, minor_employee, make_shift, make_context
    ):
        shift1 = make_shift(
            employee="Bobby",
            date_str="2024-01-15",
            start_time="08:00",
            end_time="11:00",
            total_hours=3.0,
        )
        shift2 = make_shift(
            employee="Bobby",
            date_str="2024-01-15",
            start_time="14:00",
            end_time="17:00",
            total_hours=3.0,
        )

        context = make_context(
            employees={"Bobby": minor_employee},
            shifts=[shift1, shift2],
        )

        result = ComplianceResult()
        validator = MinorRestrictionsValidator()
        validator.validate(context, result)

        daily_violations = [v for v in result.violations if v.rule_type == ViolationType.MINOR_DAILY_HOURS]
        assert len(daily_violations) == 0

    def test_multiple_shifts_sum_hours_for_weekly_total(
        self, default_rules, minor_employee, make_shift, make_context
    ):
        shifts = []
        for i, day in enumerate(["Monday", "Tuesday", "Wednesday"]):
            # Morning shift
            shifts.append(make_shift(
                employee="Bobby",
                date_str=f"2024-01-{15 + i}",
                start_time="07:00",
                end_time="10:30",
                total_hours=3.5,
                day_of_week=day,
            ))
            # Afternoon shift
            shifts.append(make_shift(
                employee="Bobby",
                date_str=f"2024-01-{15 + i}",
                start_time="14:00",
                end_time="17:30",
                total_hours=3.5,
                day_of_week=day,
            ))
        for i, day in enumerate(["Thursday", "Friday"], start=3):
            shifts.append(make_shift(
                employee="Bobby",
                date_str=f"2024-01-{15 + i}",
                start_time="08:00",
                end_time="16:00",
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
        assert len(weekly_violations) == 0

    def test_multiple_shifts_exceed_weekly_limit(
        self, default_rules, minor_employee, make_shift, make_context
    ):
        shifts = []
        for i, day in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]):
            shifts.append(make_shift(
                employee="Bobby",
                date_str=f"2024-01-{15 + i}",
                start_time="09:00",
                end_time="16:00",
                total_hours=7.0,
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


class TestOvernightShifts:

    def test_overnight_shift_rest_violation_across_days(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        previous_shift = make_shift(
            employee="Alice",
            date_str="2024-01-14",
            start_time="18:00",
            end_time="23:30",
            total_hours=5.5,
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
        assert rest_violations[0].details["rest_hours"] == 6.5

    def test_consecutive_day_shifts_adequate_rest(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        previous_shift = make_shift(
            employee="Alice",
            date_str="2024-01-14",
            start_time="09:00",
            end_time="17:00",
            total_hours=8.0,
            day_of_week="Sunday",
        )

        current_shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="09:00",
            end_time="17:00",
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
        assert len(rest_violations) == 0


class TestCurfewBoundaries:

    def test_shift_ending_one_minute_after_curfew(
        self, default_rules, minor_employee, make_shift, make_context
    ):
        shift = make_shift(
            employee="Bobby",
            date_str="2024-01-15",
            start_time="17:00",
            end_time="22:01",
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

    def test_shift_starting_exactly_at_earliest(
        self, default_rules, minor_employee, make_shift, make_context
    ):
        shift = make_shift(
            employee="Bobby",
            date_str="2024-01-15",
            start_time="06:00",
            end_time="12:00",
            total_hours=6.0,
        )

        context = make_context(
            employees={"Bobby": minor_employee},
            shifts=[shift],
        )

        result = ComplianceResult()
        validator = MinorRestrictionsValidator()
        validator.validate(context, result)

        early_violations = [v for v in result.violations if v.rule_type == ViolationType.MINOR_EARLY_START]
        assert len(early_violations) == 0

    def test_shift_starting_one_minute_before_earliest(
        self, default_rules, minor_employee, make_shift, make_context
    ):
        shift = make_shift(
            employee="Bobby",
            date_str="2024-01-15",
            start_time="05:59",
            end_time="12:00",
            total_hours=6.0,
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

    def test_shift_ending_exactly_at_curfew_no_violation(
        self, default_rules, minor_employee, make_shift, make_context
    ):
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


class TestWeeklyHoursFullWeek:

    def test_full_seven_day_week_under_overtime(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        shifts = []
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for i, day in enumerate(days):
            shifts.append(make_shift(
                employee="Alice",
                date_str=f"2024-01-{15 + i}",
                start_time="10:00",
                end_time="15:30",
                total_hours=5.5,
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
        assert result.employee_weekly_hours.get("Alice") == 38.5

    def test_full_seven_day_week_overtime(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        shifts = []
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for i, day in enumerate(days):
            shifts.append(make_shift(
                employee="Alice",
                date_str=f"2024-01-{15 + i}",
                start_time="10:00",
                end_time="16:00",
                total_hours=6.0,
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
        assert result.employee_weekly_hours.get("Alice") == 42.0
        assert result.overtime_hours.get("Alice") == 2.0

    def test_exactly_40_hours_no_overtime(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        shifts = []
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        for i, day in enumerate(days):
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


class TestRestBetweenShiftsAcrossDays:

    def test_exact_minimum_rest_no_violation(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        previous_shift = make_shift(
            employee="Alice",
            date_str="2024-01-14",
            start_time="14:00",
            end_time="22:00",
            total_hours=8.0,
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
        assert len(rest_violations) == 0

    def test_one_minute_under_minimum_rest_violation(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        previous_shift = make_shift(
            employee="Alice",
            date_str="2024-01-14",
            start_time="14:00",
            end_time="22:30",
            total_hours=8.5,
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
        assert rest_violations[0].details["rest_hours"] == 7.5

    def test_california_10_hour_rest_requirement(
        self, california_rules, adult_employee, make_shift, make_context
    ):
        previous_shift = make_shift(
            employee="Alice",
            date_str="2024-01-14",
            start_time="13:00",
            end_time="21:00",
            total_hours=8.0,
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
            rules=california_rules,
        )

        result = ComplianceResult()
        validator = RestBetweenShiftsValidator()
        validator.validate(context, result)

        rest_violations = [v for v in result.violations if v.rule_type == ViolationType.REST_VIOLATION]
        assert len(rest_violations) == 1
        assert rest_violations[0].details["min_required"] == 10.0

    def test_multiple_consecutive_shifts_same_day(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        shift1 = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="06:00",
            end_time="10:00",
            total_hours=4.0,
            day_of_week="Monday",
        )

        shift2 = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="12:00",
            end_time="16:00",
            total_hours=4.0,
            day_of_week="Monday",
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[shift1, shift2],
        )

        result = ComplianceResult()
        validator = RestBetweenShiftsValidator()
        validator.validate(context, result)

        rest_violations = [v for v in result.violations if v.rule_type == ViolationType.REST_VIOLATION]
        assert len(rest_violations) == 1


class TestBreakRequirementsAtThreshold:

    def test_shift_exactly_5_hours_no_meal_break(
        self, default_rules, adult_employee, make_shift, make_context
    ):
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

    def test_shift_5_hours_1_minute_requires_meal_break(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="09:00",
            end_time="14:01",
            total_hours=5.017,
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

    def test_shift_exactly_4_hours_requires_rest_break(
        self, default_rules, adult_employee, make_shift, make_context
    ):
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
        assert rest_violations[0].details["breaks_needed"] == 1

    def test_shift_3_hours_59_minutes_no_rest_break(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="09:00",
            end_time="12:59",
            total_hours=3.98,
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[shift],
        )

        result = ComplianceResult()
        validator = BreakComplianceValidator()
        validator.validate(context, result)

        rest_violations = [v for v in result.violations if v.rule_type == ViolationType.REST_BREAK_REQUIRED]
        assert len(rest_violations) == 0

    def test_shift_8_hours_requires_two_rest_breaks(
        self, default_rules, adult_employee, make_shift, make_context
    ):
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
        )

        result = ComplianceResult()
        validator = BreakComplianceValidator()
        validator.validate(context, result)

        rest_violations = [v for v in result.violations if v.rule_type == ViolationType.REST_BREAK_REQUIRED]
        assert len(rest_violations) == 1
        assert rest_violations[0].details["breaks_needed"] == 2


class TestMultipleViolationsSingleShift:

    def test_minor_with_curfew_and_early_start_violation(
        self, default_rules, minor_employee, make_shift, make_context
    ):
        shift = make_shift(
            employee="Bobby",
            date_str="2024-01-15",
            start_time="05:00",
            end_time="23:00",
            total_hours=18.0,
        )

        context = make_context(
            employees={"Bobby": minor_employee},
            shifts=[shift],
        )

        result = ComplianceResult()
        validator = MinorRestrictionsValidator()
        validator.validate(context, result)

        curfew_violations = [v for v in result.violations if v.rule_type == ViolationType.MINOR_CURFEW]
        early_violations = [v for v in result.violations if v.rule_type == ViolationType.MINOR_EARLY_START]
        daily_violations = [v for v in result.violations if v.rule_type == ViolationType.MINOR_DAILY_HOURS]

        assert len(curfew_violations) == 1
        assert len(early_violations) == 1
        assert len(daily_violations) == 1

    def test_shift_with_overtime_and_break_violations(
        self, california_rules, adult_employee, make_shift, make_context
    ):
        shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="06:00",
            end_time="18:00",
            total_hours=12.0,
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[shift],
            rules=california_rules,
        )

        result = ComplianceResult()

        # Run both validators
        OvertimeValidator().validate(context, result)
        BreakComplianceValidator().validate(context, result)

        daily_ot = [v for v in result.violations if v.rule_type == ViolationType.DAILY_OVERTIME]
        meal_breaks = [v for v in result.violations if v.rule_type == ViolationType.MEAL_BREAK_REQUIRED]
        rest_breaks = [v for v in result.violations if v.rule_type == ViolationType.REST_BREAK_REQUIRED]

        assert len(daily_ot) == 1
        assert daily_ot[0].details["overtime_hours"] == 4.0
        assert len(meal_breaks) == 1
        assert len(rest_breaks) == 1

    def test_all_validators_on_problematic_shift(
        self, default_rules, minor_employee, make_shift, make_context
    ):
        shift = make_shift(
            employee="Bobby",
            date_str="2024-01-15",
            start_time="05:00",
            end_time="23:00",
            total_hours=18.0,
        )

        context = make_context(
            employees={"Bobby": minor_employee},
            shifts=[shift],
        )

        engine = ComplianceEngine()
        result = engine.validate(context)

        assert len(result.violations) >= 5


class TestZeroHourShifts:

    def test_zero_hour_shift_no_break_violations(
        self, default_rules, adult_employee, make_shift, make_context
    ):
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

    def test_zero_hour_shift_no_overtime(
        self, default_rules, adult_employee, make_shift, make_context
    ):
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
        validator = OvertimeValidator()
        validator.validate(context, result)

        assert result.employee_weekly_hours.get("Alice") == 0.0
        assert len(result.violations) == 0

    def test_zero_hour_shift_skipped_in_rest_check(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        previous_shift = make_shift(
            employee="Alice",
            date_str="2024-01-14",
            start_time="23:00",
            end_time="23:00",
            total_hours=0.0,
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
        assert len(rest_violations) == 0

    def test_minor_zero_hour_shift_no_violations(
        self, default_rules, minor_employee, make_shift, make_context
    ):
        shift = make_shift(
            employee="Bobby",
            date_str="2024-01-15",
            start_time="23:00",
            end_time="23:00",
            total_hours=0.0,
        )

        context = make_context(
            employees={"Bobby": minor_employee},
            shifts=[shift],
        )

        result = ComplianceResult()
        validator = MinorRestrictionsValidator()
        validator.validate(context, result)

        daily_violations = [v for v in result.violations if v.rule_type == ViolationType.MINOR_DAILY_HOURS]
        assert len(daily_violations) == 0


class TestShiftsStartingAtMidnight:

    def test_shift_starting_at_midnight(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="00:00",
            end_time="08:00",
            total_hours=8.0,
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[shift],
        )

        result = ComplianceResult()
        validator = OvertimeValidator()
        validator.validate(context, result)

        assert result.employee_weekly_hours.get("Alice") == 8.0

    def test_minor_shift_starting_at_midnight_early_start_violation(
        self, default_rules, minor_employee, make_shift, make_context
    ):
        shift = make_shift(
            employee="Bobby",
            date_str="2024-01-15",
            start_time="00:00",
            end_time="06:00",
            total_hours=6.0,
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
        assert early_violations[0].details["shift_start"] == "00:00"

    def test_rest_violation_with_midnight_shift(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        previous_shift = make_shift(
            employee="Alice",
            date_str="2024-01-14",
            start_time="14:00",
            end_time="22:00",
            total_hours=8.0,
            day_of_week="Sunday",
        )

        current_shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="00:00",
            end_time="08:00",
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
        assert rest_violations[0].details["rest_hours"] == 2.0

    def test_shift_ending_at_midnight(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="16:00",
            end_time="00:00",
            total_hours=8.0,
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[shift],
        )

        result = ComplianceResult()
        validator = OvertimeValidator()
        validator.validate(context, result)

        assert result.employee_weekly_hours.get("Alice") == 8.0


class TestMultipleEmployeesScenarios:

    def test_multiple_employees_different_violations(
        self, default_rules, adult_employee, minor_employee, make_shift, make_context
    ):
        adult_shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="08:00",
            end_time="18:00",
            total_hours=10.0,
        )

        minor_shift = make_shift(
            employee="Bobby",
            date_str="2024-01-15",
            start_time="18:00",
            end_time="23:00",
            total_hours=5.0,
        )

        context = make_context(
            employees={
                "Alice": adult_employee,
                "Bobby": minor_employee,
            },
            shifts=[adult_shift, minor_shift],
        )

        engine = ComplianceEngine()
        result = engine.validate(context)

        alice_violations = [v for v in result.violations if v.employee_name == "Alice"]
        bobby_violations = [v for v in result.violations if v.employee_name == "Bobby"]

        assert any(v.rule_type == ViolationType.MEAL_BREAK_REQUIRED for v in alice_violations)

        assert any(v.rule_type == ViolationType.MINOR_CURFEW for v in bobby_violations)

    def test_multiple_employees_weekly_hours_tracked_separately(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        adult_employee2 = EmployeeCompliance(
            name="Charlie",
            date_of_birth=date(1985, 3, 20),
            is_minor=False,
            hourly_rate=18.0,
        )

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
        for i, day in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]):
            shifts.append(make_shift(
                employee="Charlie",
                date_str=f"2024-01-{15 + i}",
                start_time="09:00",
                end_time="17:00",
                total_hours=8.0,
                day_of_week=day,
            ))

        context = make_context(
            employees={
                "Alice": adult_employee,
                "Charlie": adult_employee2,
            },
            shifts=shifts,
        )

        result = ComplianceResult()
        validator = OvertimeValidator()
        validator.validate(context, result)

        assert result.employee_weekly_hours.get("Alice") == 40.0
        assert result.employee_weekly_hours.get("Charlie") == 48.0

        weekly_ot = [v for v in result.violations if v.rule_type == ViolationType.WEEKLY_OVERTIME]
        assert len(weekly_ot) == 1
        assert weekly_ot[0].employee_name == "Charlie"


class TestNegativeEdgeCases:

    def test_negative_hours_treated_as_no_shift(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="09:00",
            end_time="17:00",
            total_hours=-8.0,
        )

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=[shift],
        )

        result = ComplianceResult()
        validator = BreakComplianceValidator()
        validator.validate(context, result)

        assert len(result.violations) == 0

    def test_very_long_shift_24_hours(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        shift = make_shift(
            employee="Alice",
            date_str="2024-01-15",
            start_time="00:00",
            end_time="00:00",
            total_hours=24.0,
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
        assert rest_violations[0].details["breaks_needed"] == 6

    def test_fractional_hours_calculations(
        self, default_rules, adult_employee, make_shift, make_context
    ):
        shifts = []
        for i, day in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]):
            shifts.append(make_shift(
                employee="Alice",
                date_str=f"2024-01-{15 + i}",
                start_time="09:00",
                end_time="17:06",
                total_hours=8.1,
                day_of_week=day,
            ))

        context = make_context(
            employees={"Alice": adult_employee},
            shifts=shifts,
        )

        result = ComplianceResult()
        validator = OvertimeValidator()
        validator.validate(context, result)

        assert result.employee_weekly_hours.get("Alice") == 40.5
        weekly_ot = [v for v in result.violations if v.rule_type == ViolationType.WEEKLY_OVERTIME]
        assert len(weekly_ot) == 1
        assert result.overtime_hours.get("Alice") == 0.5
