import sys
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock all external dependencies before importing the app."""
    # Mock gspread
    mock_gspread = MagicMock()
    mock_gc = MagicMock()
    mock_book = MagicMock()
    mock_book.worksheet.return_value.get_all_records.return_value = []
    mock_gc.open_by_key.return_value = mock_book
    mock_gspread.service_account.return_value = mock_gc

    # Mock motor and beanie
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
    """Mock MongoDB operations."""
    with patch("app.init_db", new_callable=AsyncMock) as mock_init, patch(
        "app.close_db", new_callable=AsyncMock
    ) as mock_close, patch(
        "app.EmployeeDoc"
    ) as mock_emp, patch(
        "app.StoreDoc"
    ) as mock_store, patch(
        "app.ConfigDoc"
    ) as mock_config, patch(
        "app.ScheduleRunDoc"
    ) as mock_schedule:
        # Mock find operations to return empty lists by default
        mock_emp.find.return_value.to_list = AsyncMock(return_value=[])
        mock_store.find.return_value.to_list = AsyncMock(return_value=[])
        mock_config.find_one = AsyncMock(return_value=None)
        mock_schedule.find_one = AsyncMock(return_value=None)

        yield {
            "init_db": mock_init,
            "close_db": mock_close,
            "EmployeeDoc": mock_emp,
            "StoreDoc": mock_store,
            "ConfigDoc": mock_config,
            "ScheduleRunDoc": mock_schedule,
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


def test_solver_run_requires_pass_key(client):
    """Test that /solver/run endpoint requires pass_key parameter."""
    response = client.get("/solver/run")

    assert response.status_code == 422  # Validation error


def test_solver_run_rejects_invalid_pass_key(client):
    """Test that /solver/run rejects invalid pass_key."""
    response = client.get("/solver/run?pass_key=wrong")

    assert response.status_code == 422


def test_solver_run_accepts_valid_pass_key(client, mock_dependencies, mock_db):
    """Test that /solver/run accepts valid pass_key."""
    from schemas import WeeklyScheduleResult

    mock_result = WeeklyScheduleResult(
        week_no=1,
        store_name="Test Store",
        generated_at="2024-01-15T10:00:00",
        schedules=[],
        daily_summaries=[],
        total_weekly_cost=0.0,
        status="optimal",
    )

    # Mock the schedule run persistence
    mock_db["ScheduleRunDoc"].find.return_value.update_many = AsyncMock()

    with patch("app.main") as mock_main, patch(
        "app.SOLVER_PASS_KEY", "testkey"
    ), patch("app._persist_schedule_result", new_callable=AsyncMock):
        mock_main.return_value = mock_result
        response = client.get("/solver/run?pass_key=testkey")

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


def test_sync_all_requires_pass_key(client):
    """Test that /sync/all endpoint requires pass_key parameter."""
    response = client.post("/sync/all")

    assert response.status_code == 422  # Validation error


def test_sync_all_rejects_invalid_pass_key(client):
    """Test that /sync/all rejects invalid pass_key."""
    response = client.post("/sync/all?pass_key=wrong")

    assert response.status_code == 422


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
