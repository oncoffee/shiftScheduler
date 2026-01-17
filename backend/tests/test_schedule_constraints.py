"""Tests for schedule constraint validation."""

import pytest
from schemas import EmployeeDaySchedule, DayScheduleSummary, WeeklyScheduleResult


# Minimum shift length in hours (matches MIN_SHIFT_PERIODS * 0.5 in model_run.py)
MIN_SHIFT_HOURS = 3.0


def validate_minimum_shift_length(schedules: list[EmployeeDaySchedule]) -> list[str]:
    """
    Validate that all shifts are either 0 hours or at least MIN_SHIFT_HOURS.
    Returns a list of violations (empty if all valid).
    """
    violations = []
    for schedule in schedules:
        if schedule.total_hours > 0 and schedule.total_hours < MIN_SHIFT_HOURS:
            violations.append(
                f"{schedule.employee_name} on {schedule.day_of_week}: "
                f"{schedule.total_hours}h (minimum is {MIN_SHIFT_HOURS}h)"
            )
    return violations


def create_mock_schedule(
    employee: str, day: str, hours: float
) -> EmployeeDaySchedule:
    """Helper to create a mock schedule entry."""
    return EmployeeDaySchedule(
        employee_name=employee,
        day_of_week=day,
        periods=[],
        total_hours=hours,
        shift_start="09:00" if hours > 0 else None,
        shift_end="17:00" if hours > 0 else None,
    )


class TestMinimumShiftConstraint:
    """Tests for minimum shift length constraint."""

    def test_zero_hours_is_valid(self):
        """An employee with 0 hours (not scheduled) is valid."""
        schedules = [create_mock_schedule("Alice", "Monday", 0)]
        violations = validate_minimum_shift_length(schedules)
        assert violations == []

    def test_minimum_hours_is_valid(self):
        """An employee with exactly 3 hours is valid."""
        schedules = [create_mock_schedule("Alice", "Monday", 3.0)]
        violations = validate_minimum_shift_length(schedules)
        assert violations == []

    def test_above_minimum_is_valid(self):
        """An employee with more than 3 hours is valid."""
        schedules = [create_mock_schedule("Alice", "Monday", 5.0)]
        violations = validate_minimum_shift_length(schedules)
        assert violations == []

    def test_half_hour_shift_is_invalid(self):
        """A 30-minute shift should be invalid."""
        schedules = [create_mock_schedule("Alice", "Monday", 0.5)]
        violations = validate_minimum_shift_length(schedules)
        assert len(violations) == 1
        assert "Alice" in violations[0]
        assert "0.5h" in violations[0]

    def test_one_hour_shift_is_invalid(self):
        """A 1-hour shift should be invalid."""
        schedules = [create_mock_schedule("Bob", "Tuesday", 1.0)]
        violations = validate_minimum_shift_length(schedules)
        assert len(violations) == 1
        assert "Bob" in violations[0]

    def test_two_hour_shift_is_invalid(self):
        """A 2-hour shift should be invalid."""
        schedules = [create_mock_schedule("Charlie", "Wednesday", 2.0)]
        violations = validate_minimum_shift_length(schedules)
        assert len(violations) == 1
        assert "Charlie" in violations[0]

    def test_mixed_valid_and_invalid_schedules(self):
        """Test with a mix of valid and invalid schedules."""
        schedules = [
            create_mock_schedule("Alice", "Monday", 4.0),   # Valid
            create_mock_schedule("Bob", "Monday", 0),       # Valid (not scheduled)
            create_mock_schedule("Charlie", "Monday", 1.5), # Invalid
            create_mock_schedule("Diana", "Tuesday", 3.0),  # Valid
            create_mock_schedule("Eve", "Tuesday", 2.5),    # Invalid
        ]
        violations = validate_minimum_shift_length(schedules)
        assert len(violations) == 2
        assert any("Charlie" in v for v in violations)
        assert any("Eve" in v for v in violations)

    def test_full_weekly_schedule_all_valid(self):
        """Test a full week schedule where all shifts are valid."""
        schedules = []
        employees = ["Alice", "Bob", "Charlie"]
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

        for emp in employees:
            for day in days:
                # Alternate between not working (0) and working (4-8 hours)
                hours = 0 if hash(f"{emp}{day}") % 2 == 0 else 4.0 + (hash(f"{emp}{day}") % 5)
                schedules.append(create_mock_schedule(emp, day, hours))

        violations = validate_minimum_shift_length(schedules)
        assert violations == []

    def test_boundary_just_under_minimum(self):
        """Test boundary case: 2.5 hours (just under 3h minimum)."""
        schedules = [create_mock_schedule("Alice", "Monday", 2.5)]
        violations = validate_minimum_shift_length(schedules)
        assert len(violations) == 1

    def test_boundary_at_minimum(self):
        """Test boundary case: exactly at 3h minimum."""
        schedules = [create_mock_schedule("Alice", "Monday", 3.0)]
        violations = validate_minimum_shift_length(schedules)
        assert violations == []


class TestWeeklyScheduleResultValidation:
    """Tests for validating complete WeeklyScheduleResult objects."""

    def test_valid_weekly_result(self):
        """A WeeklyScheduleResult with valid shifts passes validation."""
        result = WeeklyScheduleResult(
            start_date="2024-01-15",
            end_date="2024-01-21",
            store_name="Test Store",
            generated_at="2024-01-15T10:00:00",
            schedules=[
                create_mock_schedule("Alice", "Monday", 4.0),
                create_mock_schedule("Bob", "Monday", 0),
                create_mock_schedule("Alice", "Tuesday", 6.0),
            ],
            daily_summaries=[
                DayScheduleSummary(
                    day_of_week="Monday",
                    total_cost=100.0,
                    employees_scheduled=1,
                    total_labor_hours=4.0,
                ),
            ],
            total_weekly_cost=100.0,
            status="optimal",
        )
        violations = validate_minimum_shift_length(result.schedules)
        assert violations == []

    def test_invalid_weekly_result(self):
        """A WeeklyScheduleResult with short shifts fails validation."""
        result = WeeklyScheduleResult(
            start_date="2024-01-15",
            end_date="2024-01-21",
            store_name="Test Store",
            generated_at="2024-01-15T10:00:00",
            schedules=[
                create_mock_schedule("Alice", "Monday", 0.5),  # Invalid
                create_mock_schedule("Bob", "Monday", 4.0),    # Valid
            ],
            daily_summaries=[],
            total_weekly_cost=50.0,
            status="optimal",
        )
        violations = validate_minimum_shift_length(result.schedules)
        assert len(violations) == 1
        assert "Alice" in violations[0]
