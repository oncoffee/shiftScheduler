import sys
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from schemas import (
    EmployeeDaySchedule,
    ShiftPeriod,
    WeeklyScheduleResult,
    DayScheduleSummary,
)


@pytest.fixture(autouse=True)
def mock_dependencies():
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
def mock_db():
    with patch("app.init_db", new_callable=AsyncMock), patch(
        "app.close_db", new_callable=AsyncMock
    ), patch("app.EmployeeDoc") as mock_emp, patch(
        "app.StoreDoc"
    ) as mock_store, patch(
        "app.ConfigDoc"
    ) as mock_config, patch(
        "app.ScheduleRunDoc"
    ) as mock_schedule:
        mock_emp.find.return_value.to_list = AsyncMock(return_value=[])
        mock_store.find.return_value.to_list = AsyncMock(return_value=[])
        mock_config.find_one = AsyncMock(return_value=None)
        mock_schedule.find_one = AsyncMock(return_value=None)
        mock_schedule.find.return_value.update_many = AsyncMock()

        yield {
            "EmployeeDoc": mock_emp,
            "StoreDoc": mock_store,
            "ConfigDoc": mock_config,
            "ScheduleRunDoc": mock_schedule,
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

        locked_shifts = [
            {"employee_name": "Alice", "day_of_week": "Monday", "periods": [0, 1, 2, 3]}
        ]

        mock_assignment = MagicMock()
        mock_assignment.is_locked = True
        mock_assignment.total_hours = 4.0
        mock_assignment.employee_name = "Alice"
        mock_assignment.day_of_week = "Monday"
        mock_period = MagicMock()
        mock_period.period_index = 0
        mock_period.scheduled = True
        mock_assignment.periods = [mock_period]

        mock_current_schedule = MagicMock()
        mock_current_schedule.assignments = [mock_assignment]
        mock_db["ScheduleRunDoc"].find_one = AsyncMock(return_value=mock_current_schedule)

        with patch("app.main") as mock_main, patch(
            "app.SOLVER_PASS_KEY", "testkey"
        ), patch("app._persist_schedule_result", new_callable=AsyncMock):
            mock_main.return_value = mock_result
            response = client.get("/solver/run?pass_key=testkey&start_date=2024-01-15&end_date=2024-01-21")

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

        with patch("app.main") as mock_main, patch("app.SOLVER_PASS_KEY", "testkey"):
            mock_main.side_effect = ValueError(
                "Schedule is infeasible for Monday. Check locked shifts and availability."
            )
            response = client.get("/solver/run?pass_key=testkey&start_date=2024-01-15&end_date=2024-01-21")

            assert response.status_code == 400
            assert "infeasible" in response.json()["detail"].lower()

    def test_solver_returns_400_with_descriptive_message(self, client, mock_db):
        mock_db["ScheduleRunDoc"].find_one = AsyncMock(return_value=None)

        with patch("app.main") as mock_main, patch("app.SOLVER_PASS_KEY", "testkey"):
            mock_main.side_effect = ValueError("Solver failed for Tuesday with status 3")
            response = client.get("/solver/run?pass_key=testkey&start_date=2024-01-15&end_date=2024-01-21")

            assert response.status_code == 400
            assert "Tuesday" in response.json()["detail"]


class TestLockedShiftsExtraction:

    def test_locked_shifts_extracted_from_current_schedule(self, client, mock_db):
        mock_period_0 = MagicMock()
        mock_period_0.period_index = 0
        mock_period_0.scheduled = True
        mock_period_1 = MagicMock()
        mock_period_1.period_index = 1
        mock_period_1.scheduled = True
        mock_period_2 = MagicMock()
        mock_period_2.period_index = 2
        mock_period_2.scheduled = False

        mock_assignment = MagicMock()
        mock_assignment.is_locked = True
        mock_assignment.total_hours = 1.0
        mock_assignment.employee_name = "Alice"
        mock_assignment.day_of_week = "Monday"
        mock_assignment.periods = [mock_period_0, mock_period_1, mock_period_2]

        mock_current_schedule = MagicMock()
        mock_current_schedule.assignments = [mock_assignment]
        mock_db["ScheduleRunDoc"].find_one = AsyncMock(return_value=mock_current_schedule)

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
            "app.SOLVER_PASS_KEY", "testkey"
        ), patch("app._persist_schedule_result", new_callable=AsyncMock):
            mock_main.return_value = mock_result
            response = client.get("/solver/run?pass_key=testkey&start_date=2024-01-15&end_date=2024-01-21")

            assert response.status_code == 200
            mock_main.assert_called_once()
            call_args = mock_main.call_args
            locked_shifts = call_args.kwargs.get("locked_shifts")
            assert locked_shifts is not None
            assert len(locked_shifts) == 1
            assert locked_shifts[0]["employee_name"] == "Alice"
            assert locked_shifts[0]["day_of_week"] == "Monday"
            assert locked_shifts[0]["periods"] == [0, 1]

    def test_unlocked_shifts_not_extracted(self, client, mock_db):
        mock_assignment = MagicMock()
        mock_assignment.is_locked = False
        mock_assignment.total_hours = 4.0
        mock_assignment.employee_name = "Bob"
        mock_assignment.day_of_week = "Monday"

        mock_current_schedule = MagicMock()
        mock_current_schedule.assignments = [mock_assignment]
        mock_db["ScheduleRunDoc"].find_one = AsyncMock(return_value=mock_current_schedule)

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
            "app.SOLVER_PASS_KEY", "testkey"
        ), patch("app._persist_schedule_result", new_callable=AsyncMock):
            mock_main.return_value = mock_result
            response = client.get("/solver/run?pass_key=testkey&start_date=2024-01-15&end_date=2024-01-21")

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

        mock_current_schedule = MagicMock()
        mock_current_schedule.assignments = [mock_assignment]
        mock_db["ScheduleRunDoc"].find_one = AsyncMock(return_value=mock_current_schedule)

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
            "app.SOLVER_PASS_KEY", "testkey"
        ), patch("app._persist_schedule_result", new_callable=AsyncMock):
            mock_main.return_value = mock_result
            response = client.get("/solver/run?pass_key=testkey&start_date=2024-01-15&end_date=2024-01-21")

            assert response.status_code == 200
            call_args = mock_main.call_args
            locked_shifts = call_args.kwargs.get("locked_shifts")
            assert locked_shifts is None or locked_shifts == []
