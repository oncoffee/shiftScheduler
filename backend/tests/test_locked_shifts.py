import sys
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from schemas import (
    EmployeeDaySchedule,
    ShiftPeriod,
    WeeklyScheduleResult,
    DayScheduleSummary,
)


# Module-level mocks to prevent reimport issues
_mock_gspread = MagicMock()
_mock_gc = MagicMock()
_mock_book = MagicMock()
_mock_book.worksheet.return_value.get_all_records.return_value = []
_mock_gc.open_by_key.return_value = _mock_book
_mock_gspread.service_account.return_value = _mock_gc

_mock_motor = MagicMock()


@pytest.fixture(scope="module", autouse=True)
def mock_dependencies():
    """Mock all external dependencies before importing the app."""
    with patch.dict(
        sys.modules,
        {
            "gspread": _mock_gspread,
            "motor": _mock_motor,
            "motor.motor_asyncio": _mock_motor,
        },
    ):
        yield


def _create_find_chain_mock(return_value=None):
    """Create a mock that supports the full find chain."""
    if return_value is None:
        return_value = []

    find_result = MagicMock()
    find_result.count = AsyncMock(return_value=len(return_value) if isinstance(return_value, list) else 0)

    sort_result = MagicMock()
    skip_result = MagicMock()
    limit_result = MagicMock()

    find_result.sort = MagicMock(return_value=sort_result)
    sort_result.skip = MagicMock(return_value=skip_result)
    skip_result.limit = MagicMock(return_value=limit_result)
    limit_result.to_list = AsyncMock(return_value=return_value)

    find_result.to_list = AsyncMock(return_value=return_value)
    sort_result.to_list = AsyncMock(return_value=return_value)
    find_result.update_many = AsyncMock()

    return find_result


class _QueryFieldMock:
    """A simple mock field that supports comparison operators for Beanie query building."""

    def __ge__(self, other):
        return MagicMock()

    def __le__(self, other):
        return MagicMock()

    def __gt__(self, other):
        return MagicMock()

    def __lt__(self, other):
        return MagicMock()

    def __eq__(self, other):
        return MagicMock()

    def __ne__(self, other):
        return MagicMock()


def _create_document_mock_with_fields():
    """Create a mock Document class with comparable field attributes."""
    mock_doc = MagicMock()
    mock_doc.date = _QueryFieldMock()
    mock_doc.store_name = _QueryFieldMock()
    mock_doc.employee_name = _QueryFieldMock()
    mock_doc.is_current = _QueryFieldMock()
    mock_doc.is_locked = _QueryFieldMock()
    mock_doc.total_hours = _QueryFieldMock()
    return mock_doc


@pytest.fixture
def mock_db(mock_dependencies):
    """Mock MongoDB operations."""
    mock_assignment = _create_document_mock_with_fields()
    mock_daily_summary = _create_document_mock_with_fields()
    mock_schedule = _create_document_mock_with_fields()

    with patch("app.init_db", new_callable=AsyncMock), patch(
        "app.close_db", new_callable=AsyncMock
    ), patch("app.EmployeeDoc") as mock_emp, patch(
        "app.StoreDoc"
    ) as mock_store, patch(
        "app.ConfigDoc"
    ) as mock_config, patch(
        "app.ScheduleRunDoc", mock_schedule
    ), patch(
        "app.ComplianceRuleDoc"
    ) as mock_compliance, patch(
        "app.AssignmentDoc", mock_assignment
    ), patch(
        "app.DailySummaryDoc", mock_daily_summary
    ), patch(
        "app.AssignmentEditDoc"
    ) as mock_edit, patch(
        "db.ConfigDoc"
    ) as mock_db_config, patch(
        "db.ComplianceRuleDoc"
    ) as mock_db_compliance, patch(
        "db.StoreDoc"
    ) as mock_db_store:
        mock_emp.find.return_value.to_list = AsyncMock(return_value=[])
        mock_store.find.return_value.to_list = AsyncMock(return_value=[])
        mock_store.find_one = AsyncMock(return_value=None)
        mock_config.find_one = AsyncMock(return_value=None)
        mock_schedule.find_one = AsyncMock(return_value=None)
        mock_schedule.find = MagicMock(return_value=_create_find_chain_mock([]))
        mock_compliance.find_one = AsyncMock(return_value=None)
        mock_assignment.find = MagicMock(return_value=_create_find_chain_mock([]))
        mock_assignment.find_one = AsyncMock(return_value=None)
        mock_daily_summary.find = MagicMock(return_value=_create_find_chain_mock([]))
        mock_daily_summary.find_one = AsyncMock(return_value=None)

        # Mock db module imports (used by compliance engine)
        mock_db_config.find_one = AsyncMock(return_value=None)
        mock_db_compliance.find_one = AsyncMock(return_value=None)
        mock_db_store.find_one = AsyncMock(return_value=None)

        yield {
            "EmployeeDoc": mock_emp,
            "StoreDoc": mock_store,
            "ConfigDoc": mock_config,
            "ScheduleRunDoc": mock_schedule,
            "ComplianceRuleDoc": mock_compliance,
            "AssignmentDoc": mock_assignment,
            "DailySummaryDoc": mock_daily_summary,
            "AssignmentEditDoc": mock_edit,
        }


@pytest.fixture
def client(mock_dependencies, mock_db):
    from fastapi.testclient import TestClient
    from app import app

    return TestClient(app)


def create_schedule_with_periods(
    employee: str, day: str, hours: float, is_locked: bool = False
) -> EmployeeDaySchedule:
    periods = []
    num_periods = int(hours * 2)
    for i in range(num_periods):
        periods.append(
            ShiftPeriod(
                period_index=i,
                start_time=f"{9 + i // 2:02d}:{(i % 2) * 30:02d}",
                end_time=f"{9 + (i + 1) // 2:02d}:{((i + 1) % 2) * 30:02d}",
                scheduled=True,
            )
        )
    return EmployeeDaySchedule(
        employee_name=employee,
        day_of_week=day,
        periods=periods,
        total_hours=hours,
        shift_start="09:00" if hours > 0 else None,
        shift_end=f"{9 + int(hours):02d}:{int((hours % 1) * 60):02d}" if hours > 0 else None,
        is_locked=is_locked,
    )


def _create_mock_assignment_doc(
    employee_name: str,
    date: str,
    day_of_week: str,
    total_hours: float,
    shift_start: str,
    shift_end: str,
    is_locked: bool = False,
    is_short_shift: bool = False,
    num_periods: int = 8,
):
    """Create a mock AssignmentDoc for the separate collection."""
    assignment = MagicMock()
    assignment.employee_name = employee_name
    assignment.day_of_week = day_of_week
    assignment.date = date
    assignment.total_hours = total_hours
    assignment.shift_start = shift_start
    assignment.shift_end = shift_end
    assignment.is_short_shift = is_short_shift
    assignment.is_locked = is_locked
    assignment.store_name = "Test Store"
    assignment.periods = []
    for i in range(num_periods):
        p = MagicMock()
        p.period_index = i
        p.scheduled = True
        p.start_time = f"{9 + i // 2:02d}:{(i % 2) * 30:02d}"
        p.end_time = f"{9 + (i + 1) // 2:02d}:{((i + 1) % 2) * 30:02d}"
        p.is_locked = False
        p.is_break = False
        assignment.periods.append(p)
    return assignment


def _create_full_mock_schedule_run(
    store_name: str = "Test Store",
    assignments: list = None,
    has_alice_locked: bool = False,
    has_bob: bool = False,
):
    """Helper to create a properly populated mock schedule run (metadata only)."""
    from datetime import datetime

    mock_schedule_run = MagicMock()
    mock_schedule_run.start_date = datetime(2024, 1, 15)
    mock_schedule_run.end_date = datetime(2024, 1, 21)
    mock_schedule_run.store_name = store_name
    mock_schedule_run.generated_at = datetime(2024, 1, 15, 10, 0, 0)
    mock_schedule_run.total_weekly_cost = 100.0
    mock_schedule_run.total_dummy_worker_cost = 0.0
    mock_schedule_run.total_short_shift_penalty = 0.0
    mock_schedule_run.status = "optimal"
    mock_schedule_run.has_warnings = False
    mock_schedule_run.is_edited = False
    mock_schedule_run.last_edited_at = None

    return mock_schedule_run


def _get_mock_assignments_for_schedule(has_alice_locked: bool = False, has_bob: bool = False):
    """Get list of mock assignment docs for separate collection queries."""
    result_assignments = []
    if has_alice_locked:
        alice = _create_mock_assignment_doc(
            employee_name="Alice",
            date="2024-01-15",
            day_of_week="Monday",
            total_hours=4.0,
            shift_start="09:00",
            shift_end="13:00",
            is_locked=True,
            num_periods=8,
        )
        result_assignments.append(alice)

    if has_bob:
        bob = _create_mock_assignment_doc(
            employee_name="Bob",
            date="2024-01-15",
            day_of_week="Monday",
            total_hours=3.0,
            shift_start="09:00",
            shift_end="12:00",
            is_locked=False,
            is_short_shift=True,
            num_periods=6,
        )
        result_assignments.append(bob)

    return result_assignments


class TestLockedShiftsPreservation:

    def test_solver_preserves_locked_state_in_response(self, client, mock_db):
        mock_result = WeeklyScheduleResult(
            start_date="2024-01-15",
            end_date="2024-01-21",
            store_name="Test Store",
            generated_at="2024-01-15T10:00:00",
            schedules=[
                create_schedule_with_periods("Alice", "Monday", 4.0),
                create_schedule_with_periods("Bob", "Monday", 3.0),
            ],
            daily_summaries=[
                DayScheduleSummary(
                    day_of_week="Monday",
                    total_cost=100.0,
                    employees_scheduled=2,
                    total_labor_hours=7.0,
                )
            ],
            total_weekly_cost=100.0,
            status="optimal",
        )

        # Create mock schedule for getting locked shifts (before solver)
        mock_assignment = MagicMock()
        mock_assignment.is_locked = True
        mock_assignment.total_hours = 4.0
        mock_assignment.employee_name = "Alice"
        mock_assignment.day_of_week = "Monday"
        mock_assignment.date = "2024-01-15"
        mock_assignment.shift_start = "09:00"
        mock_assignment.shift_end = "13:00"
        mock_assignment.is_short_shift = False
        mock_period = MagicMock()
        mock_period.period_index = 0
        mock_period.scheduled = True
        mock_period.start_time = "09:00"
        mock_period.end_time = "09:30"
        mock_period.is_locked = False
        mock_period.is_break = False
        mock_assignment.periods = [mock_period]

        # Create schedule run metadata (no embedded assignments)
        result_mock = _create_full_mock_schedule_run()
        # Initial mock for getting locked shifts has assignments on it (old format for extraction only)
        initial_mock_schedule = MagicMock()
        initial_mock_schedule.assignments = [mock_assignment]

        # Use side_effect to return different mocks for multiple calls
        mock_db["ScheduleRunDoc"].find_one = AsyncMock(
            side_effect=[initial_mock_schedule, result_mock, result_mock]
        )

        mock_assignments = _get_mock_assignments_for_schedule(has_alice_locked=True, has_bob=True)
        mock_db["AssignmentDoc"].find = MagicMock(return_value=_create_find_chain_mock(mock_assignments))
        mock_db["DailySummaryDoc"].find = MagicMock(return_value=_create_find_chain_mock([]))

        with patch("app.main") as mock_main, patch(
            "app._persist_schedule_result", new_callable=AsyncMock
        ), patch("app._run_compliance_validation", new_callable=AsyncMock):
            mock_main.return_value = mock_result
            response = client.get("/solver/run?start_date=2024-01-15&end_date=2024-01-21")

            assert response.status_code == 200
            data = response.json()

            alice_schedule = next(
                s for s in data["schedules"] if s["employee_name"] == "Alice"
            )
            assert alice_schedule["is_locked"] is True

            bob_schedule = next(
                s for s in data["schedules"] if s["employee_name"] == "Bob"
            )
            assert bob_schedule["is_locked"] is False


class TestSolverErrorHandling:

    def test_solver_returns_400_on_infeasible_model(self, client, mock_db):
        mock_db["ScheduleRunDoc"].find_one = AsyncMock(return_value=None)

        with patch("app.main") as mock_main:
            mock_main.side_effect = ValueError(
                "Schedule is infeasible for Monday. Check locked shifts and availability."
            )
            response = client.get("/solver/run?start_date=2024-01-15&end_date=2024-01-21")

            assert response.status_code == 400
            assert "infeasible" in response.json()["detail"].lower()

    def test_solver_returns_400_with_descriptive_message(self, client, mock_db):
        mock_db["ScheduleRunDoc"].find_one = AsyncMock(return_value=None)

        with patch("app.main") as mock_main:
            mock_main.side_effect = ValueError("Solver failed for Tuesday with status 3")
            response = client.get("/solver/run?start_date=2024-01-15&end_date=2024-01-21")

            assert response.status_code == 400
            assert "Tuesday" in response.json()["detail"]


class TestLockedShiftsExtraction:

    def test_locked_shifts_extracted_from_current_schedule(self, client, mock_db):
        mock_period_0 = MagicMock()
        mock_period_0.period_index = 0
        mock_period_0.scheduled = True
        mock_period_0.start_time = "09:00"
        mock_period_0.end_time = "09:30"
        mock_period_0.is_locked = False
        mock_period_0.is_break = False
        mock_period_1 = MagicMock()
        mock_period_1.period_index = 1
        mock_period_1.scheduled = True
        mock_period_1.start_time = "09:30"
        mock_period_1.end_time = "10:00"
        mock_period_1.is_locked = False
        mock_period_1.is_break = False
        mock_period_2 = MagicMock()
        mock_period_2.period_index = 2
        mock_period_2.scheduled = False
        mock_period_2.start_time = "10:00"
        mock_period_2.end_time = "10:30"
        mock_period_2.is_locked = False
        mock_period_2.is_break = False

        mock_assignment = MagicMock()
        mock_assignment.is_locked = True
        mock_assignment.total_hours = 1.0
        mock_assignment.employee_name = "Alice"
        mock_assignment.day_of_week = "Monday"
        mock_assignment.date = "2024-01-15"
        mock_assignment.shift_start = "09:00"
        mock_assignment.shift_end = "10:00"
        mock_assignment.is_short_shift = True
        mock_assignment.periods = [mock_period_0, mock_period_1, mock_period_2]

        mock_current_schedule = MagicMock()
        mock_current_schedule.assignments = [mock_assignment]

        # Create a full mock for the result after persist (metadata only)
        result_mock = _create_full_mock_schedule_run()
        mock_db["ScheduleRunDoc"].find_one = AsyncMock(
            side_effect=[mock_current_schedule, result_mock, result_mock]
        )

        mock_db["AssignmentDoc"].find = MagicMock(return_value=_create_find_chain_mock([mock_assignment]))
        mock_db["DailySummaryDoc"].find = MagicMock(return_value=_create_find_chain_mock([]))

        mock_result = WeeklyScheduleResult(
            start_date="2024-01-15",
            end_date="2024-01-21",
            store_name="Test Store",
            generated_at="2024-01-15T10:00:00",
            schedules=[create_schedule_with_periods("Alice", "Monday", 1.0)],
            daily_summaries=[],
            total_weekly_cost=50.0,
            status="optimal",
        )

        with patch("app.main") as mock_main, patch(
            "app._persist_schedule_result", new_callable=AsyncMock
        ), patch("app._run_compliance_validation", new_callable=AsyncMock):
            mock_main.return_value = mock_result
            response = client.get("/solver/run?start_date=2024-01-15&end_date=2024-01-21")

            assert response.status_code == 200
            mock_main.assert_called_once()
            call_args = mock_main.call_args
            locked_shifts = call_args.kwargs.get("locked_shifts")
            assert locked_shifts is not None
            assert len(locked_shifts) == 1
            assert locked_shifts[0]["employee_name"] == "Alice"
            assert locked_shifts[0]["date"] == "2024-01-15"
            assert locked_shifts[0]["periods"] == [0, 1]

    def test_unlocked_shifts_not_extracted(self, client, mock_db):
        mock_assignment = MagicMock()
        mock_assignment.is_locked = False
        mock_assignment.total_hours = 4.0
        mock_assignment.employee_name = "Bob"
        mock_assignment.day_of_week = "Monday"
        mock_assignment.date = "2024-01-15"
        mock_assignment.shift_start = "09:00"
        mock_assignment.shift_end = "13:00"
        mock_assignment.is_short_shift = False
        mock_assignment.periods = []

        mock_current_schedule = MagicMock()
        mock_current_schedule.assignments = [mock_assignment]

        # Create a full mock for the result after persist (metadata only)
        result_mock = _create_full_mock_schedule_run()
        mock_db["ScheduleRunDoc"].find_one = AsyncMock(
            side_effect=[mock_current_schedule, result_mock, result_mock]
        )

        mock_db["AssignmentDoc"].find = MagicMock(return_value=_create_find_chain_mock([]))
        mock_db["DailySummaryDoc"].find = MagicMock(return_value=_create_find_chain_mock([]))

        mock_result = WeeklyScheduleResult(
            start_date="2024-01-15",
            end_date="2024-01-21",
            store_name="Test Store",
            generated_at="2024-01-15T10:00:00",
            schedules=[],
            daily_summaries=[],
            total_weekly_cost=0.0,
            status="optimal",
        )

        with patch("app.main") as mock_main, patch(
            "app._persist_schedule_result", new_callable=AsyncMock
        ), patch("app._run_compliance_validation", new_callable=AsyncMock):
            mock_main.return_value = mock_result
            response = client.get("/solver/run?start_date=2024-01-15&end_date=2024-01-21")

            assert response.status_code == 200
            call_args = mock_main.call_args
            locked_shifts = call_args.kwargs.get("locked_shifts")
            assert locked_shifts is None or locked_shifts == []

    def test_zero_hour_locked_shifts_not_extracted(self, client, mock_db):
        mock_assignment = MagicMock()
        mock_assignment.is_locked = True
        mock_assignment.total_hours = 0
        mock_assignment.employee_name = "Charlie"
        mock_assignment.day_of_week = "Tuesday"
        mock_assignment.date = "2024-01-16"
        mock_assignment.shift_start = None
        mock_assignment.shift_end = None
        mock_assignment.is_short_shift = False
        mock_assignment.periods = []

        mock_current_schedule = MagicMock()
        mock_current_schedule.assignments = [mock_assignment]

        # Create a full mock for the result after persist (metadata only)
        result_mock = _create_full_mock_schedule_run()
        mock_db["ScheduleRunDoc"].find_one = AsyncMock(
            side_effect=[mock_current_schedule, result_mock, result_mock]
        )

        mock_db["AssignmentDoc"].find = MagicMock(return_value=_create_find_chain_mock([]))
        mock_db["DailySummaryDoc"].find = MagicMock(return_value=_create_find_chain_mock([]))

        mock_result = WeeklyScheduleResult(
            start_date="2024-01-15",
            end_date="2024-01-21",
            store_name="Test Store",
            generated_at="2024-01-15T10:00:00",
            schedules=[],
            daily_summaries=[],
            total_weekly_cost=0.0,
            status="optimal",
        )

        with patch("app.main") as mock_main, patch(
            "app._persist_schedule_result", new_callable=AsyncMock
        ), patch("app._run_compliance_validation", new_callable=AsyncMock):
            mock_main.return_value = mock_result
            response = client.get("/solver/run?start_date=2024-01-15&end_date=2024-01-21")

            assert response.status_code == 200
            call_args = mock_main.call_args
            locked_shifts = call_args.kwargs.get("locked_shifts")
            assert locked_shifts is None or locked_shifts == []
