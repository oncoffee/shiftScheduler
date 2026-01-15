import sys
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_gspread_module():
    """Mock gspread before any imports."""
    mock_gspread = MagicMock()
    mock_gc = MagicMock()
    mock_book = MagicMock()
    mock_book.worksheet.return_value.get_all_records.return_value = []
    mock_gc.open_by_key.return_value = mock_book
    mock_gspread.service_account.return_value = mock_gc

    with patch.dict(sys.modules, {"gspread": mock_gspread}):
        yield


def test_fix_column_name_strips_whitespace(mock_gspread_module):
    """Test that fix_column_name strips leading/trailing whitespace."""
    from data_import import fix_column_name

    assert fix_column_name("  name  ") == "name"
    assert fix_column_name("\ttest\n") == "test"


def test_fix_column_name_converts_to_lowercase(mock_gspread_module):
    """Test that fix_column_name converts to lowercase."""
    from data_import import fix_column_name

    assert fix_column_name("Name") == "name"
    assert fix_column_name("UPPERCASE") == "uppercase"
    assert fix_column_name("MixedCase") == "mixedcase"


def test_fix_column_name_replaces_spaces_with_underscores(mock_gspread_module):
    """Test that fix_column_name replaces spaces with underscores."""
    from data_import import fix_column_name

    assert fix_column_name("first name") == "first_name"
    assert fix_column_name("a b c") == "a_b_c"


def test_fix_column_name_combined_transformations(mock_gspread_module):
    """Test fix_column_name with combined transformations."""
    from data_import import fix_column_name

    assert fix_column_name("  First Name  ") == "first_name"
    assert fix_column_name("Day Of Week") == "day_of_week"


def test_pre_row_for_parsing_transforms_keys(mock_gspread_module):
    """Test that pre_row_for_parsing transforms dictionary keys."""
    from data_import import pre_row_for_parsing

    row = {"First Name": "John", "Last Name": "Doe"}
    result = pre_row_for_parsing(row)

    assert "first_name" in result
    assert "last_name" in result
    assert result["first_name"] == "John"
    assert result["last_name"] == "Doe"


def test_pre_row_for_parsing_preserves_values(mock_gspread_module):
    """Test that pre_row_for_parsing preserves original values."""
    from data_import import pre_row_for_parsing

    row = {"Age": 25, "Active": True, "Score": 95.5}
    result = pre_row_for_parsing(row)

    assert result["age"] == 25
    assert result["active"] is True
    assert result["score"] == 95.5


def test_pre_row_for_parsing_empty_dict(mock_gspread_module):
    """Test that pre_row_for_parsing handles empty dictionary."""
    from data_import import pre_row_for_parsing

    result = pre_row_for_parsing({})

    assert result == {}


def test_store_model_validates_correctly(mock_gspread_module):
    """Test Store model validation."""
    from data_import import Store

    store = Store(
        week_no=1,
        store_name="Main Store",
        day_of_week="Monday",
        start_time="09:00",
        end_time="17:00"
    )

    assert store.week_no == 1
    assert store.store_name == "Main Store"
    assert store.day_of_week == "Monday"


def test_employee_schedule_model_validates_correctly(mock_gspread_module):
    """Test EmployeeSchedule model validation."""
    from data_import import EmployeeSchedule

    schedule = EmployeeSchedule(
        employee_name="John",
        day_of_week="Tuesday",
        availability="09:00 - 17:00"
    )

    assert schedule.employee_name == "John"
    assert schedule.day_of_week == "Tuesday"
    assert schedule.availability == "09:00 - 17:00"


def test_employee_model_validates_correctly(mock_gspread_module):
    """Test Employee model validation."""
    from data_import import Employee

    employee = Employee(
        employee_name="Alice",
        hourly_rate=15.50,
        minimum_hours_per_week=20,
        minimum_hours=4,
        maximum_hours=8
    )

    assert employee.employee_name == "Alice"
    assert employee.hourly_rate == 15.50
    assert employee.minimum_hours_per_week == 20
    assert employee.minimum_hours == 4
    assert employee.maximum_hours == 8
