import pytest
from datetime import time, datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock


class MockUserDoc:
    def __init__(self, role="admin"):
        self.id = "test-user-id"
        self.email = "test@example.com"
        self.google_id = "google-123"
        self.name = "Test User"
        self.picture_url = None
        self.role = role
        self.refresh_token_hash = None
        self.refresh_token_expires_at = None
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.last_login_at = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def override_auth_dependencies():
    from app import app
    from auth.dependencies import get_current_user, require_admin, require_editor_or_admin

    mock_user = MockUserDoc(role="admin")

    async def mock_get_current_user():
        return mock_user

    async def mock_require_admin():
        return mock_user

    async def mock_require_editor_or_admin():
        return mock_user

    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[require_admin] = mock_require_admin
    app.dependency_overrides[require_editor_or_admin] = mock_require_editor_or_admin

    yield mock_user

    app.dependency_overrides.clear()


@pytest.fixture
def mock_gspread():
    with patch("data_import.gspread") as mock_gs:
        mock_gc = MagicMock()
        mock_book = MagicMock()

        mock_book.worksheet.return_value.get_all_records.return_value = []
        mock_gc.open_by_key.return_value = mock_book
        mock_gs.service_account.return_value = mock_gc

        yield mock_gs


@pytest.fixture
def sample_store_times():
    return {
        "start": time(9, 0),
        "end": time(17, 0),
        "day": "Monday"
    }


@pytest.fixture
def sample_employee_availability():
    return {
        "name": "John",
        "day": "Monday",
        "start": "09:00",
        "end": "14:00"
    }
