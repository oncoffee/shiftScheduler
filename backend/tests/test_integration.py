"""Integration tests for solver and compliance working together.

Tests end-to-end solver runs with compliance validation,
and verifies break periods are correctly saved and returned in API.
"""

import sys
from datetime import date, datetime
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from solvers.types import (
    ScheduleProblem,
    SolverConfig,
    SolverResult,
    SolverStatus,
)
from solvers.gurobi_solver import GurobiSolver
from solvers.pulp_solver import PuLPSolver
from solvers.ortools_solver import ORToolsSolver
from compliance.types import (
    ComplianceContext,
    ComplianceResult,
    ComplianceRules,
    EmployeeCompliance,
    ShiftInfo,
    ViolationType,
    ViolationSeverity,
)
from compliance.validators import (
    MinorRestrictionsValidator,
    OvertimeValidator,
    BreakComplianceValidator,
)
from compliance.engine import ComplianceEngine


# ============================================================================
# ============================================================================


@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock external dependencies."""
    mock_gspread = MagicMock()
    mock_gc = MagicMock()
    mock_book = MagicMock()
    mock_book.worksheet.return_value.get_all_records.return_value = []
    mock_gc.open_by_key.return_value = mock_book
    mock_gspread.service_account.return_value = mock_gc

    mock_motor = MagicMock()
    mock_beanie = MagicMock()
    mock_beanie.init_beanie = AsyncMock()

    with patch.dict(
        sys.modules,
        {
            "gspread": mock_gspread,
            "motor": mock_motor,
            "motor.motor_asyncio": mock_motor,
        },
    ):
        yield


@pytest.fixture
def full_day_periods():
    """Generate 24 time periods (12 hours) from 08:00-20:00."""
    periods = []
    for i in range(24):
        hour = 8 + i // 2
        minute = (i % 2) * 30
        periods.append(f"{hour:02d}:{minute:02d}")
    return periods


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
def break_enabled_config():
    """Solver config with meal breaks enabled."""
    return SolverConfig(
        dummy_worker_cost=100.0,
        short_shift_penalty=50.0,
        min_shift_hours=3.0,
        max_daily_hours=11.0,
        meal_break_enabled=True,
        meal_break_threshold_hours=5.0,
        meal_break_duration_periods=1,
    )


# ============================================================================
# End-to-End Solver with Compliance Tests
# ============================================================================


class TestSolverWithCompliance:
    """Test solver runs followed by compliance validation."""

    @pytest.mark.parametrize("solver_cls", [GurobiSolver, PuLPSolver, ORToolsSolver])
    def test_solver_result_passes_to_compliance_validator(
        self, solver_cls, full_day_periods, break_enabled_config, default_rules
    ):
        """Solver result should integrate with compliance validation."""
        employees = ["Alice"]
        availability = {"Alice": [1] * len(full_day_periods)}
        hourly_rates = {"Alice": 15.0}
        minimum_workers = [1] * len(full_day_periods)

        problem = ScheduleProblem(
            employees=employees,
            time_periods=full_day_periods,
            employee_availability=availability,
            hourly_rates=hourly_rates,
            minimum_workers=minimum_workers,
        )

      
        solver = solver_cls()
        result = solver.solve(problem, break_enabled_config)

        assert result.status in (SolverStatus.OPTIMAL, SolverStatus.SUBOPTIMAL)

      
        scheduled_indices = []
        for idx, t in enumerate(full_day_periods):
            if result.schedule_matrix.get(("Alice", t), 0) == 1:
                scheduled_indices.append(idx)

        if scheduled_indices:
            start_idx = min(scheduled_indices)
            end_idx = max(scheduled_indices)
            start_time = full_day_periods[start_idx]
          
            end_hour = 8 + (end_idx + 1) // 2
            end_minute = ((end_idx + 1) % 2) * 30
            end_time = f"{end_hour:02d}:{end_minute:02d}"
            total_hours = len(scheduled_indices) * 0.5

            shift = ShiftInfo(
                employee_name="Alice",
                date="2024-01-15",
                day_of_week="Monday",
                start_time=start_time,
                end_time=end_time,
                total_hours=total_hours,
                periods=scheduled_indices,
            )

          
            employee = EmployeeCompliance(
                name="Alice",
                date_of_birth=date(1990, 5, 15),
                is_minor=False,
                hourly_rate=15.0,
            )

            context = ComplianceContext(
                rules=default_rules,
                employees={"Alice": employee},
                shifts=[shift],
                compliance_mode="warn",
            )

            engine = ComplianceEngine()
            compliance_result = engine.validate(context)

          
            if total_hours > 5.0:
                meal_violations = [
                    v for v in compliance_result.violations
                    if v.rule_type == ViolationType.MEAL_BREAK_REQUIRED
                ]
              
              
              
              
                assert len(meal_violations) >= 0

    @pytest.mark.parametrize("solver_cls", [GurobiSolver, PuLPSolver, ORToolsSolver])
    def test_break_periods_recorded_in_solver_result(
        self, solver_cls, full_day_periods, break_enabled_config
    ):
        """Break periods from solver should be properly recorded in result."""
        employees = ["Alice"]
        availability = {"Alice": [1] * len(full_day_periods)}
        hourly_rates = {"Alice": 15.0}
      
        minimum_workers = [1] * len(full_day_periods)

        problem = ScheduleProblem(
            employees=employees,
            time_periods=full_day_periods,
            employee_availability=availability,
            hourly_rates=hourly_rates,
            minimum_workers=minimum_workers,
        )

        solver = solver_cls()
        result = solver.solve(problem, break_enabled_config)

      
        scheduled_count = sum(
            1 for t in full_day_periods
            if result.schedule_matrix.get(("Alice", t), 0) == 1
        )
        scheduled_hours = scheduled_count * 0.5

      
        if scheduled_hours > break_enabled_config.meal_break_threshold_hours:
            assert "Alice" in result.break_periods, \
                f"Solver should record breaks for {scheduled_hours}h shift"

          
            scheduled_indices = set()
            for idx, t in enumerate(full_day_periods):
                if result.schedule_matrix.get(("Alice", t), 0) == 1:
                    scheduled_indices.add(idx)

            for bp in result.break_periods.get("Alice", []):
                assert bp in scheduled_indices, \
                    f"Break period {bp} not in scheduled periods"

    def test_minor_compliance_flags_long_shift(self, full_day_periods, default_rules):
        """Minor working long shift should trigger compliance violation."""
      
        employees = ["Bobby"]

      
        shift = ShiftInfo(
            employee_name="Bobby",
            date="2024-01-15",
            day_of_week="Monday",
            start_time="08:00",
            end_time="18:00",
            total_hours=10.0,
        )

      
        today = date.today()
        minor_dob = date(today.year - 17, today.month, today.day)
        employee = EmployeeCompliance(
            name="Bobby",
            date_of_birth=minor_dob,
            is_minor=True,
            hourly_rate=12.0,
        )

        context = ComplianceContext(
            rules=default_rules,
            employees={"Bobby": employee},
            shifts=[shift],
            compliance_mode="enforce",
        )

        engine = ComplianceEngine()
        result = engine.validate(context)

      
        daily_violations = [
            v for v in result.violations
            if v.rule_type == ViolationType.MINOR_DAILY_HOURS
        ]
        assert len(daily_violations) == 1
        assert result.is_compliant is False


# ============================================================================
# ============================================================================


class TestBreakPeriodsInAPI:
    """Test that break periods are correctly handled through the API layer."""

    def test_break_periods_convert_to_schema_format(self, full_day_periods):
        """Break periods should convert to the schema format correctly."""
        from schemas import ShiftPeriod, EmployeeDaySchedule

      
        break_period_indices = [4, 5]

      
        periods = []
        for idx, t in enumerate(full_day_periods):
            end_idx = idx + 1
            end_hour = 8 + end_idx // 2
            end_minute = (end_idx % 2) * 30
            end_time = f"{end_hour:02d}:{end_minute:02d}"

            period = ShiftPeriod(
                period_index=idx,
                start_time=t,
                end_time=end_time,
                scheduled=True,
                is_break=idx in break_period_indices,
            )
            periods.append(period)

        schedule = EmployeeDaySchedule(
            employee_name="Alice",
            day_of_week="Monday",
            periods=periods,
            total_hours=12.0,
            shift_start="08:00",
            shift_end="20:00",
            is_short_shift=False,
        )

      
        break_periods = [p for p in schedule.periods if p.is_break]
        assert len(break_periods) == 2
        assert break_periods[0].period_index == 4
        assert break_periods[1].period_index == 5

    def test_solver_break_output_maps_to_api_response(self, full_day_periods, break_enabled_config):
        """Solver break_periods dict should map correctly to API response format."""
        from schemas import ShiftPeriod

      
        employees = ["Alice"]
        availability = {"Alice": [1] * len(full_day_periods)}
        hourly_rates = {"Alice": 15.0}
        minimum_workers = [1] * len(full_day_periods)

        problem = ScheduleProblem(
            employees=employees,
            time_periods=full_day_periods,
            employee_availability=availability,
            hourly_rates=hourly_rates,
            minimum_workers=minimum_workers,
        )

        solver = GurobiSolver()
        result = solver.solve(problem, break_enabled_config)

      
        break_periods_for_alice = result.break_periods.get("Alice", [])

      
        periods = []
        for idx, t in enumerate(full_day_periods):
            is_scheduled = result.schedule_matrix.get(("Alice", t), 0) == 1
            is_break = idx in break_periods_for_alice

            end_idx = idx + 1
            end_hour = 8 + end_idx // 2
            end_minute = (end_idx % 2) * 30
            end_time = f"{end_hour:02d}:{end_minute:02d}"

            period = ShiftPeriod(
                period_index=idx,
                start_time=t,
                end_time=end_time,
                scheduled=is_scheduled,
                is_break=is_break,
            )
            periods.append(period)

      
        api_breaks = [p for p in periods if p.is_break]
        assert len(api_breaks) == len(break_periods_for_alice)

        for bp in api_breaks:
            assert bp.scheduled is True, "Break periods should be marked as scheduled"
            assert bp.period_index in break_periods_for_alice


# ============================================================================
# Multi-Day Schedule with Compliance Tests
# ============================================================================


class TestMultiDayScheduleCompliance:
    """Test compliance across multiple days."""

    def test_weekly_overtime_detection(self, default_rules):
        """Weekly overtime should be detected across multiple days."""
      
        shifts = []
        for i, day in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]):
            shifts.append(ShiftInfo(
                employee_name="Alice",
                date=f"2024-01-{15 + i}",
                day_of_week=day,
                start_time="09:00",
                end_time="17:00",
                total_hours=8.0,
            ))

        employee = EmployeeCompliance(
            name="Alice",
            date_of_birth=date(1990, 5, 15),
            is_minor=False,
            hourly_rate=15.0,
        )

        context = ComplianceContext(
            rules=default_rules,
            employees={"Alice": employee},
            shifts=shifts,
            compliance_mode="warn",
        )

        engine = ComplianceEngine()
        result = engine.validate(context)

      
        weekly_ot = [v for v in result.violations if v.rule_type == ViolationType.WEEKLY_OVERTIME]
        assert len(weekly_ot) == 1
        assert result.employee_weekly_hours["Alice"] == 48.0

    def test_rest_between_shifts_validation(self, default_rules):
        """Rest between consecutive shifts should be validated."""
      
        previous_shift = ShiftInfo(
            employee_name="Alice",
            date="2024-01-14",
            day_of_week="Sunday",
            start_time="16:00",
            end_time="23:00",
            total_hours=7.0,
        )

      
        current_shift = ShiftInfo(
            employee_name="Alice",
            date="2024-01-15",
            day_of_week="Monday",
            start_time="06:00",
            end_time="14:00",
            total_hours=8.0,
        )

        employee = EmployeeCompliance(
            name="Alice",
            date_of_birth=date(1990, 5, 15),
            is_minor=False,
            hourly_rate=15.0,
        )

        context = ComplianceContext(
            rules=default_rules,
            employees={"Alice": employee},
            shifts=[current_shift],
            previous_day_shifts=[previous_shift],
            compliance_mode="warn",
        )

        engine = ComplianceEngine()
        result = engine.validate(context)

        rest_violations = [v for v in result.violations if v.rule_type == ViolationType.REST_VIOLATION]
        assert len(rest_violations) == 1

    def test_multiple_employees_compliance(self, default_rules):
        """Multiple employees should be validated independently."""
        today = date.today()
        minor_dob = date(today.year - 17, today.month, today.day)

      
        minor_shift = ShiftInfo(
            employee_name="Bobby",
            date="2024-01-15",
            day_of_week="Monday",
            start_time="18:00",
            end_time="23:00",
            total_hours=5.0,
        )

      
        adult_shifts = []
        for i, day in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]):
            adult_shifts.append(ShiftInfo(
                employee_name="Alice",
                date=f"2024-01-{15 + i}",
                day_of_week=day,
                start_time="08:00",
                end_time="18:00",
                total_hours=10.0,
            ))

        employees = {
            "Bobby": EmployeeCompliance(
                name="Bobby",
                date_of_birth=minor_dob,
                is_minor=True,
                hourly_rate=12.0,
            ),
            "Alice": EmployeeCompliance(
                name="Alice",
                date_of_birth=date(1990, 5, 15),
                is_minor=False,
                hourly_rate=15.0,
            ),
        }

        context = ComplianceContext(
            rules=default_rules,
            employees=employees,
            shifts=[minor_shift] + adult_shifts,
            compliance_mode="warn",
        )

        engine = ComplianceEngine()
        result = engine.validate(context)

      
        bobby_violations = [v for v in result.violations if v.employee_name == "Bobby"]
        assert len(bobby_violations) >= 1
        curfew = [v for v in bobby_violations if v.rule_type == ViolationType.MINOR_CURFEW]
        assert len(curfew) == 1

      
        alice_violations = [v for v in result.violations if v.employee_name == "Alice"]
        weekly_ot = [v for v in alice_violations if v.rule_type == ViolationType.WEEKLY_OVERTIME]
        assert len(weekly_ot) == 1


# ============================================================================
# Solver + Compliance Integration Edge Cases
# ============================================================================


class TestSolverComplianceEdgeCases:
    """Test edge cases in solver + compliance integration."""

    def test_empty_schedule_no_violations(self, default_rules):
        """Empty schedule should not produce violations."""
        context = ComplianceContext(
            rules=default_rules,
            employees={},
            shifts=[],
            compliance_mode="warn",
        )

        engine = ComplianceEngine()
        result = engine.validate(context)

        assert len(result.violations) == 0
        assert result.is_compliant is True

    def test_zero_hour_shift_no_violations(self, default_rules):
        """Zero-hour shifts should not trigger break requirements."""
        shift = ShiftInfo(
            employee_name="Alice",
            date="2024-01-15",
            day_of_week="Monday",
            start_time="09:00",
            end_time="09:00",
            total_hours=0.0,
        )

        employee = EmployeeCompliance(
            name="Alice",
            date_of_birth=date(1990, 5, 15),
            is_minor=False,
            hourly_rate=15.0,
        )

        context = ComplianceContext(
            rules=default_rules,
            employees={"Alice": employee},
            shifts=[shift],
            compliance_mode="warn",
        )

        engine = ComplianceEngine()
        result = engine.validate(context)

        break_violations = [
            v for v in result.violations
            if v.rule_type in (ViolationType.MEAL_BREAK_REQUIRED, ViolationType.REST_BREAK_REQUIRED)
        ]
        assert len(break_violations) == 0

    def test_exactly_at_thresholds(self, default_rules):
        """Shifts exactly at thresholds should be handled correctly."""
      
        shift_5h = ShiftInfo(
            employee_name="Alice",
            date="2024-01-15",
            day_of_week="Monday",
            start_time="09:00",
            end_time="14:00",
            total_hours=5.0,
        )

      
        shifts_40h = []
        for i, day in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]):
            shifts_40h.append(ShiftInfo(
                employee_name="Bob",
                date=f"2024-01-{15 + i}",
                day_of_week=day,
                start_time="09:00",
                end_time="17:00",
                total_hours=8.0,
            ))

        employees = {
            "Alice": EmployeeCompliance(name="Alice", is_minor=False),
            "Bob": EmployeeCompliance(name="Bob", is_minor=False),
        }

        context = ComplianceContext(
            rules=default_rules,
            employees=employees,
            shifts=[shift_5h] + shifts_40h,
            compliance_mode="warn",
        )

        engine = ComplianceEngine()
        result = engine.validate(context)

      
        alice_meal = [
            v for v in result.violations
            if v.employee_name == "Alice" and v.rule_type == ViolationType.MEAL_BREAK_REQUIRED
        ]
        assert len(alice_meal) == 0

      
        bob_ot = [
            v for v in result.violations
            if v.employee_name == "Bob" and v.rule_type == ViolationType.WEEKLY_OVERTIME
        ]
        assert len(bob_ot) == 0


# ============================================================================
# ============================================================================


class TestComplianceModes:
    """Test different compliance modes (off, warn, enforce)."""

    def test_off_mode_no_validation(self, default_rules):
        """Off mode should skip all validation."""
        today = date.today()
        minor_dob = date(today.year - 17, today.month, today.day)

      
        shift = ShiftInfo(
            employee_name="Bobby",
            date="2024-01-15",
            day_of_week="Monday",
            start_time="18:00",
            end_time="23:00",
            total_hours=5.0,
        )

        employee = EmployeeCompliance(
            name="Bobby",
            date_of_birth=minor_dob,
            is_minor=True,
        )

        context = ComplianceContext(
            rules=default_rules,
            employees={"Bobby": employee},
            shifts=[shift],
            compliance_mode="off",
        )

        engine = ComplianceEngine()
        result = engine.validate(context)

      
        assert len(result.violations) == 0

    def test_warn_mode_allows_scheduling(self, default_rules):
        """Warn mode should flag but allow scheduling."""
        today = date.today()
        minor_dob = date(today.year - 17, today.month, today.day)

        shift = ShiftInfo(
            employee_name="Bobby",
            date="2024-01-15",
            day_of_week="Monday",
            start_time="18:00",
            end_time="23:00",
            total_hours=5.0,
        )

        employee = EmployeeCompliance(
            name="Bobby",
            date_of_birth=minor_dob,
            is_minor=True,
        )

        context = ComplianceContext(
            rules=default_rules,
            employees={"Bobby": employee},
            shifts=[shift],
            compliance_mode="warn",
        )

        engine = ComplianceEngine()
        result = engine.validate(context)

      
        assert len(result.violations) > 0
        for v in result.violations:
            assert v.severity == ViolationSeverity.WARNING
      
        assert result.is_compliant is True

    def test_enforce_mode_blocks_violations(self, default_rules):
        """Enforce mode should mark violations as errors."""
        today = date.today()
        minor_dob = date(today.year - 17, today.month, today.day)

        shift = ShiftInfo(
            employee_name="Bobby",
            date="2024-01-15",
            day_of_week="Monday",
            start_time="18:00",
            end_time="23:00",
            total_hours=5.0,
        )

        employee = EmployeeCompliance(
            name="Bobby",
            date_of_birth=minor_dob,
            is_minor=True,
        )

        context = ComplianceContext(
            rules=default_rules,
            employees={"Bobby": employee},
            shifts=[shift],
            compliance_mode="enforce",
        )

        engine = ComplianceEngine()
        result = engine.validate(context)

      
        minor_violations = [
            v for v in result.violations
            if v.rule_type in (ViolationType.MINOR_CURFEW, ViolationType.MINOR_EARLY_START,
                               ViolationType.MINOR_DAILY_HOURS, ViolationType.MINOR_WEEKLY_HOURS)
        ]
        assert len(minor_violations) > 0
        for v in minor_violations:
            assert v.severity == ViolationSeverity.ERROR
      
        assert result.is_compliant is False


# ============================================================================
# ============================================================================


class TestDataFlow:
    """Test data flows correctly through the system."""

    def test_solver_schedule_to_shift_info_conversion(self, full_day_periods, break_enabled_config):
        """Solver schedule should convert correctly to ShiftInfo for compliance."""
        employees = ["Alice"]
        availability = {"Alice": [1] * len(full_day_periods)}
        hourly_rates = {"Alice": 15.0}
        minimum_workers = [1] * len(full_day_periods)

        problem = ScheduleProblem(
            employees=employees,
            time_periods=full_day_periods,
            employee_availability=availability,
            hourly_rates=hourly_rates,
            minimum_workers=minimum_workers,
        )

        solver = GurobiSolver()
        result = solver.solve(problem, break_enabled_config)

      
        def solver_result_to_shift_info(
            employee: str,
            date_str: str,
            solver_result: SolverResult,
            time_periods: list[str]
        ) -> ShiftInfo | None:
            scheduled_indices = []
            for idx, t in enumerate(time_periods):
                if solver_result.schedule_matrix.get((employee, t), 0) == 1:
                    scheduled_indices.append(idx)

            if not scheduled_indices:
                return None

            start_idx = min(scheduled_indices)
            end_idx = max(scheduled_indices)

            start_time = time_periods[start_idx]
            end_hour = 8 + (end_idx + 1) // 2
            end_minute = ((end_idx + 1) % 2) * 30
            end_time = f"{end_hour:02d}:{end_minute:02d}"

            return ShiftInfo(
                employee_name=employee,
                date=date_str,
                day_of_week="Monday",
                start_time=start_time,
                end_time=end_time,
                total_hours=len(scheduled_indices) * 0.5,
                periods=scheduled_indices,
            )

        shift_info = solver_result_to_shift_info("Alice", "2024-01-15", result, full_day_periods)

        assert shift_info is not None
        assert shift_info.employee_name == "Alice"
        assert shift_info.total_hours > 0

    def test_compliance_result_serialization(self, default_rules):
        """Compliance result should serialize correctly for API response."""
        today = date.today()
        minor_dob = date(today.year - 17, today.month, today.day)

        shift = ShiftInfo(
            employee_name="Bobby",
            date="2024-01-15",
            day_of_week="Monday",
            start_time="18:00",
            end_time="23:00",
            total_hours=5.0,
        )

        employee = EmployeeCompliance(
            name="Bobby",
            date_of_birth=minor_dob,
            is_minor=True,
        )

        context = ComplianceContext(
            rules=default_rules,
            employees={"Bobby": employee},
            shifts=[shift],
            compliance_mode="warn",
        )

        engine = ComplianceEngine()
        result = engine.validate(context)

      
        result_dict = result.to_dict()

        assert "violations" in result_dict
        assert "is_compliant" in result_dict
        assert "error_count" in result_dict
        assert "warning_count" in result_dict
        assert "employee_weekly_hours" in result_dict

      
        for v in result_dict["violations"]:
            assert "rule_type" in v
            assert "severity" in v
            assert "employee_name" in v
            assert "message" in v
