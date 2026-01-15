import pytest
from datetime import time
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_gspread():
    """Mock gspread to avoid Google Sheets API calls during tests."""
    with patch("data_import.gspread") as mock_gs:
        mock_gc = MagicMock()
        mock_book = MagicMock()

        # Mock worksheet data
        mock_book.worksheet.return_value.get_all_records.return_value = []
        mock_gc.open_by_key.return_value = mock_book
        mock_gs.service_account.return_value = mock_gc

        yield mock_gs


@pytest.fixture
def sample_store_times():
    """Sample store opening times for testing."""
    return {
        "start": time(9, 0),
        "end": time(17, 0),
        "day": "Monday"
    }


@pytest.fixture
def sample_employee_availability():
    """Sample employee availability for testing."""
    return {
        "name": "John",
        "day": "Monday",
        "start": "09:00",
        "end": "14:00"
    }
