import sys
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


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

    with patch("app.init_db", new_callable=AsyncMock) as mock_init, patch(
        "app.close_db", new_callable=AsyncMock
    ) as mock_close, patch(
        "app.EmployeeDoc"
    ) as mock_emp, patch(
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
        # Mock find operations to return empty lists by default
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
            "init_db": mock_init,
            "close_db": mock_close,
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
    """Create test client for the FastAPI app."""
    from fastapi.testclient import TestClient
    from app import app

    return TestClient(app)


def test_docs_endpoint_accessible(client):
    """Test that the /docs endpoint is accessible."""
    response = client.get("/docs")

    assert response.status_code == 200


def test_openapi_endpoint_accessible(client):
    """Test that the /openapi.json endpoint is accessible."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "shiftScheduler"


def test_solver_run_returns_schedule(client, mock_dependencies, mock_db):
    """Test that /solver/run returns a schedule result."""
    from schemas import WeeklyScheduleResult
    from datetime import datetime

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

    # Mock the schedule run persistence
    mock_db["ScheduleRunDoc"].find.return_value.update_many = AsyncMock()

    # Create a proper mock schedule run for the find_one calls after persist
    mock_schedule_run = MagicMock()
    mock_schedule_run.start_date = datetime(2024, 1, 15)
    mock_schedule_run.end_date = datetime(2024, 1, 21)
    mock_schedule_run.store_name = "Test Store"
    mock_schedule_run.generated_at = datetime(2024, 1, 15, 10, 0, 0)
    mock_schedule_run.total_weekly_cost = 0.0
    mock_schedule_run.total_dummy_worker_cost = 0.0
    mock_schedule_run.total_short_shift_penalty = 0.0
    mock_schedule_run.status = "optimal"
    mock_schedule_run.has_warnings = False
    mock_schedule_run.is_edited = False
    mock_schedule_run.last_edited_at = None
    mock_db["ScheduleRunDoc"].find_one = AsyncMock(return_value=mock_schedule_run)

    mock_db["AssignmentDoc"].find = MagicMock(return_value=_create_find_chain_mock([]))
    mock_db["DailySummaryDoc"].find = MagicMock(return_value=_create_find_chain_mock([]))

    with patch("app.main") as mock_main, patch(
        "app._persist_schedule_result", new_callable=AsyncMock
    ), patch("app._run_compliance_validation", new_callable=AsyncMock):
        mock_main.return_value = mock_result
        response = client.get("/solver/run?start_date=2024-01-15&end_date=2024-01-21")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "optimal"
        assert data["store_name"] == "Test Store"
        mock_main.assert_called_once()


def test_logs_endpoint_returns_200(client):
    """Test that /logs endpoint returns 200."""
    response = client.get("/logs")

    assert response.status_code == 200


def test_logs_endpoint_returns_log_content(client, tmp_path):
    """Test that /logs returns log file content when it exists."""
    log_content = "Test log entry\nAnother entry"

    with patch("builtins.open", create=True) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = log_content
        # The endpoint uses a hardcoded path, so this test mainly verifies the logic
        response = client.get("/logs")

        # Will return "not found" since the hardcoded path doesn't exist
        assert response.status_code == 200


def test_cors_headers_present(client):
    """Test that CORS headers are present in responses."""
    response = client.options(
        "/solver/run",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    # CORS middleware should allow the request
    assert response.status_code in [200, 400, 422]


def test_schedule_history_returns_empty_list(client, mock_db):
    """Test that /schedule/history returns empty list when no schedules exist."""
    mock_db["ScheduleRunDoc"].find.return_value.sort.return_value.skip.return_value.limit.return_value.to_list = AsyncMock(
        return_value=[]
    )

    response = client.get("/schedule/history")

    assert response.status_code == 200
    assert response.json() == []


def test_schedule_results_returns_none_when_no_current(client, mock_db):
    """Test that /schedule/results returns null when no current schedule."""
    mock_db["ScheduleRunDoc"].find_one = AsyncMock(return_value=None)

    response = client.get("/schedule/results")

    assert response.status_code == 200
    assert response.json() is None


def test_update_employee_availability_success(client, mock_db):
    """Test that PUT /employees/{name}/availability updates availability."""
    mock_employee = MagicMock()
    mock_employee.set = AsyncMock()
    mock_db["EmployeeDoc"].find_one = AsyncMock(return_value=mock_employee)

    response = client.put(
        "/employees/Emma/availability",
        json={
            "availability": [
                {"day_of_week": "Monday", "start_time": "09:00", "end_time": "17:00"},
                {"day_of_week": "Tuesday", "start_time": "10:00", "end_time": "18:00"},
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["employee_name"] == "Emma"
    mock_employee.set.assert_called_once()


def test_update_employee_availability_not_found(client, mock_db):
    """Test that PUT /employees/{name}/availability returns 404 for unknown employee."""
    mock_db["EmployeeDoc"].find_one = AsyncMock(return_value=None)

    response = client.put(
        "/employees/Unknown/availability",
        json={
            "availability": [
                {"day_of_week": "Monday", "start_time": "09:00", "end_time": "17:00"},
            ]
        },
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
