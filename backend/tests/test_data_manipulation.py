import sys
from datetime import time, datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest
import pandas as pd


# Mock the data_import module before importing data_manipulation
@pytest.fixture(autouse=True)
def mock_data_import():
    mock_gspread = MagicMock()
    mock_gc = MagicMock()
    mock_book = MagicMock()
    mock_book.worksheet.return_value.get_all_records.return_value = []
    mock_gc.open_by_key.return_value = mock_book
    mock_gspread.service_account.return_value = mock_gc

    with patch.dict(sys.modules, {"gspread": mock_gspread}):
        with patch("gspread.service_account", return_value=mock_gc):
            yield


def test_putting_store_time_in_df_creates_correct_periods(mock_data_import):
    """Test that store time DataFrame has correct number of 30-min periods."""
    # Import here after mocking
    from data_manipulation import putting_store_time_in_df

    start = time(9, 0)
    end = time(17, 0)
    day = "Monday"

    df = putting_store_time_in_df(day, start, end)

    # 8 hours = 16 periods of 30 minutes
    assert len(df) == 16
    assert "Time" in df.columns
    assert "Period" in df.columns
    assert "day_of_week" in df.columns


def test_putting_store_time_in_df_correct_day_of_week(mock_data_import):
    """Test that day_of_week column is set correctly."""
    from data_manipulation import putting_store_time_in_df

    start = time(10, 0)
    end = time(12, 0)
    day = "Saturday"

    df = putting_store_time_in_df(day, start, end)

    assert all(df["day_of_week"] == "Saturday")


def test_putting_store_time_in_df_periods_start_at_zero(mock_data_import):
    """Test that periods start at 0 and increment correctly."""
    from data_manipulation import putting_store_time_in_df

    start = time(9, 0)
    end = time(11, 0)
    day = "Tuesday"

    df = putting_store_time_in_df(day, start, end)

    assert df["Period"].tolist() == [0, 1, 2, 3]


def test_putting_store_time_in_df_times_are_correct(mock_data_import):
    """Test that time slots are 30 minutes apart."""
    from data_manipulation import putting_store_time_in_df

    start = time(9, 0)
    end = time(10, 30)
    day = "Wednesday"

    df = putting_store_time_in_df(day, start, end)

    times = df["Time"].tolist()
    assert times[0] == time(9, 0)
    assert times[1] == time(9, 30)
    assert times[2] == time(10, 0)


def test_creating_employee_df_has_employee_column(mock_data_import):
    """Test that employee DataFrame has the employee name as a column."""
    from data_manipulation import creating_employee_df

    df = creating_employee_df("Alice", "Monday", "09:00", "12:00")

    assert "Alice" in df.columns
    assert all(df["Alice"] == 1)


def test_creating_employee_df_correct_columns(mock_data_import):
    """Test that employee DataFrame has correct columns."""
    from data_manipulation import creating_employee_df

    df = creating_employee_df("Bob", "Friday", "10:00", "14:00")

    assert list(df.columns) == ["day_of_week", "Time", "Bob"]


def test_creating_employee_df_correct_period_count(mock_data_import):
    """Test that employee DataFrame has correct number of periods."""
    from data_manipulation import creating_employee_df

    # 4 hours = 8 periods
    df = creating_employee_df("Charlie", "Thursday", "08:00", "12:00")

    assert len(df) == 8


def test_creating_employee_df_handles_pm_times(mock_data_import):
    """Test that employee DataFrame handles PM times correctly."""
    from data_manipulation import creating_employee_df

    df = creating_employee_df("Diana", "Sunday", "14:00", "18:00")

    assert len(df) == 8
    assert df["Time"].iloc[0] == time(14, 0)


def test_putting_store_time_empty_when_start_equals_end(mock_data_import):
    """Test that DataFrame is empty when start equals end time."""
    from data_manipulation import putting_store_time_in_df

    start = time(9, 0)
    end = time(9, 0)
    day = "Monday"

    df = putting_store_time_in_df(day, start, end)

    assert len(df) == 0
