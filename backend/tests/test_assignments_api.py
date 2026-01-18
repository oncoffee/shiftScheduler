"""
Tests for the new separate assignments collection API.
"""
import sys
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


# Module-level mock to prevent reimport issues
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
    """Create a mock that supports the full find chain: .count(), .sort().skip().limit().to_list()"""
    if return_value is None:
        return_value = []

    find_result = MagicMock()

    # Support .count()
    find_result.count = AsyncMock(return_value=len(return_value) if isinstance(return_value, list) else 0)

    # Support .sort(...).skip(...).limit(...).to_list()
    sort_result = MagicMock()
    skip_result = MagicMock()
    limit_result = MagicMock()

    find_result.sort = MagicMock(return_value=sort_result)
    sort_result.skip = MagicMock(return_value=skip_result)
    skip_result.limit = MagicMock(return_value=limit_result)
    limit_result.to_list = AsyncMock(return_value=return_value)

    # Also support simpler chains
    find_result.to_list = AsyncMock(return_value=return_value)
    sort_result.to_list = AsyncMock(return_value=return_value)

    return find_result


@pytest.fixture
def mock_db(mock_dependencies):
    """Mock MongoDB operations for assignments API."""
    with patch("app.init_db", new_callable=AsyncMock) as mock_init, \
         patch("app.close_db", new_callable=AsyncMock) as mock_close, \
         patch("app.EmployeeDoc") as mock_emp, \
         patch("app.StoreDoc") as mock_store, \
         patch("app.ConfigDoc") as mock_config, \
         patch("app.ScheduleRunDoc") as mock_schedule, \
         patch("app.AssignmentDoc") as mock_assignment, \
         patch("app.DailySummaryDoc") as mock_daily_summary, \
         patch("app.AssignmentEditDoc") as mock_edit:

        # Mock find operations for standard docs
        mock_emp.find.return_value.to_list = AsyncMock(return_value=[])
        mock_store.find.return_value.to_list = AsyncMock(return_value=[])
        mock_store.find_one = AsyncMock(return_value=None)
        mock_config.find_one = AsyncMock(return_value=None)
        mock_schedule.find_one = AsyncMock(return_value=None)

        # Mock AssignmentDoc with full chain support
        mock_assignment.find = MagicMock(return_value=_create_find_chain_mock([]))
        mock_assignment.find_one = AsyncMock(return_value=None)
        mock_assignment.get = AsyncMock(return_value=None)

        # Mock DailySummaryDoc with full chain support
        mock_daily_summary.find = MagicMock(return_value=_create_find_chain_mock([]))
        mock_daily_summary.find_one = AsyncMock(return_value=None)

        # Mock AssignmentEditDoc with full chain support
        mock_edit.find = MagicMock(return_value=_create_find_chain_mock([]))

        yield {
            "init_db": mock_init,
            "close_db": mock_close,
            "EmployeeDoc": mock_emp,
            "StoreDoc": mock_store,
            "ConfigDoc": mock_config,
            "ScheduleRunDoc": mock_schedule,
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


class TestGetAssignments:
    """Tests for GET /assignments endpoint."""

    def test_returns_empty_list_when_no_assignments(self, client, mock_db):
        """Should return paginated response with empty items when no assignments exist."""
        response = client.get("/assignments")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert "limit" in data
        assert "offset" in data

    def test_filters_by_store_name(self, client, mock_db):
        """Should filter assignments by store_name parameter."""
        mock_assignment = MagicMock()
        mock_assignment.id = "507f1f77bcf86cd799439011"
        mock_assignment.employee_name = "Emma"
        mock_assignment.date = "2026-01-20"
        mock_assignment.day_of_week = "Monday"
        mock_assignment.store_name = "TestStore"
        mock_assignment.shift_start = "09:00"
        mock_assignment.shift_end = "17:00"
        mock_assignment.total_hours = 8.0
        mock_assignment.is_short_shift = False
        mock_assignment.is_locked = False
        mock_assignment.source = "solver"
        mock_assignment.periods = []
        mock_assignment.created_at = datetime.now(timezone.utc)
        mock_assignment.updated_at = datetime.now(timezone.utc)
        mock_assignment.solver_run_id = None

        mock_db["AssignmentDoc"].find = MagicMock(
            return_value=_create_find_chain_mock([mock_assignment])
        )

        response = client.get("/assignments?store_name=TestStore")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["store_name"] == "TestStore"
        assert data["items"][0]["employee_name"] == "Emma"

    def test_filters_by_date_range(self, client, mock_db):
        """Should filter assignments by date range."""
        response = client.get("/assignments?start_date=2026-01-20&end_date=2026-01-26")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_filters_by_employee_name(self, client, mock_db):
        """Should filter assignments by employee_name."""
        response = client.get("/assignments?employee_name=Emma")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_validates_date_format(self, client, mock_db):
        """Should reject invalid date format."""
        response = client.get("/assignments?start_date=invalid-date")

        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]


class TestGetDailySummaries:
    """Tests for GET /daily-summaries endpoint."""

    def test_returns_empty_list_when_no_summaries(self, client, mock_db):
        """Should return paginated response with empty items when no summaries exist."""
        response = client.get("/daily-summaries")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_filters_by_store_and_date(self, client, mock_db):
        """Should filter summaries by store and date range."""
        response = client.get("/daily-summaries?store_name=TestStore&start_date=2026-01-20&end_date=2026-01-26")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestGetScheduleCurrent:
    """Tests for GET /schedule/current endpoint."""

    def test_handles_missing_store(self, client, mock_db):
        """Should handle case when no store exists."""
        mock_db["StoreDoc"].find_one = AsyncMock(return_value=None)

        response = client.get("/schedule/current")

        # Either 200 (null), 400 (validation), or 404 (not found) is acceptable
        assert response.status_code in [200, 400, 404]


class TestUpdateAssignmentDirect:
    """Tests for PATCH /assignments/{id} endpoint."""

    def test_returns_404_for_nonexistent_assignment(self, client, mock_db):
        """Should return 404 when assignment not found."""
        mock_db["AssignmentDoc"].get = AsyncMock(return_value=None)

        response = client.patch(
            "/assignments/507f1f77bcf86cd799439011",
            json={"shift_start": "10:00", "shift_end": "18:00"}
        )

        assert response.status_code == 404

    def test_update_requires_valid_object_id(self, client, mock_db):
        """Should return 400 for invalid ObjectId format."""
        response = client.patch(
            "/assignments/invalid-id",
            json={"is_locked": True}
        )

        assert response.status_code == 400
        assert "Invalid ID format" in response.json()["detail"]


class TestDeleteAssignmentDirect:
    """Tests for DELETE /assignments/{id} endpoint."""

    def test_returns_404_for_nonexistent_assignment(self, client, mock_db):
        """Should return 404 when assignment not found."""
        mock_db["AssignmentDoc"].get = AsyncMock(return_value=None)

        response = client.delete("/assignments/507f1f77bcf86cd799439011")

        assert response.status_code == 404

    def test_delete_requires_valid_object_id(self, client, mock_db):
        """Should return 400 for invalid ObjectId format."""
        response = client.delete("/assignments/invalid-id")

        assert response.status_code == 400
        assert "Invalid ID format" in response.json()["detail"]


class TestGetAssignmentEdits:
    """Tests for GET /assignment-edits endpoint."""

    def test_returns_empty_list_when_no_edits(self, client, mock_db):
        """Should return paginated response with empty items when no edits exist."""
        response = client.get("/assignment-edits")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_filters_by_store_and_employee(self, client, mock_db):
        """Should filter edits by store and employee."""
        response = client.get("/assignment-edits?store_name=TestStore&employee_name=Emma")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_supports_pagination(self, client, mock_db):
        """Should support limit and offset parameters."""
        response = client.get("/assignment-edits?limit=10&offset=5")

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 5


class TestLegacyEndpoints:
    """Tests for legacy schedule endpoints that interact with separate collections."""

    def test_toggle_lock_requires_valid_schedule_id(self, client, mock_db):
        """Should return 400 for invalid schedule ID format."""
        response = client.patch(
            "/schedule/nonexistent123/lock",
            json={
                "employee_name": "Emma",
                "date": "2026-01-20",
                "is_locked": True
            }
        )

        assert response.status_code == 400
        assert "Invalid" in response.json()["detail"]

    def test_toggle_lock_returns_404_when_not_found(self, client, mock_db):
        """Should return 404 when schedule not found."""
        mock_db["ScheduleRunDoc"].get = AsyncMock(return_value=None)

        response = client.patch(
            "/schedule/507f1f77bcf86cd799439011/lock",
            json={
                "employee_name": "Emma",
                "date": "2026-01-20",
                "is_locked": True
            }
        )

        assert response.status_code == 404
