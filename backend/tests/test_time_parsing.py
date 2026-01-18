import pytest
from datetime import date

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from db.sync import parse_availability, parse_date_of_birth


class TestConvertTime12HourFormat:

    def test_12_00_am_converts_to_00_00(self):
        result = parse_availability("12:00 AM - 1:00 AM")
        assert result is not None
        start, end = result
        assert start == "00:00", f"Expected 00:00, got {start}"

    def test_12_00_pm_stays_as_12_00(self):
        result = parse_availability("12:00 PM - 1:00 PM")
        assert result is not None
        start, end = result
        assert start == "12:00", f"Expected 12:00, got {start}"

    def test_12_30_am_converts_to_00_30(self):
        result = parse_availability("12:30 AM - 1:30 AM")
        assert result is not None
        start, end = result
        assert start == "00:30", f"Expected 00:30, got {start}"

    def test_12_30_pm_stays_as_12_30(self):
        result = parse_availability("12:30 PM - 1:30 PM")
        assert result is not None
        start, end = result
        assert start == "12:30", f"Expected 12:30, got {start}"

    def test_12_45_am_converts_to_00_45(self):
        result = parse_availability("12:45 AM - 1:45 AM")
        assert result is not None
        start, end = result
        assert start == "00:45", f"Expected 00:45, got {start}"

    def test_12_59_am_converts_to_00_59(self):
        result = parse_availability("12:59 AM - 1:59 AM")
        assert result is not None
        start, end = result
        assert start == "00:59", f"Expected 00:59, got {start}"


class TestBoundaryTimes:

    def test_11_59_pm_converts_to_23_59(self):
        result = parse_availability("10:00 PM - 11:59 PM")
        assert result is not None
        start, end = result
        assert end == "23:59", f"Expected 23:59, got {end}"

    def test_1_00_am_converts_to_01_00(self):
        result = parse_availability("1:00 AM - 2:00 AM")
        assert result is not None
        start, end = result
        assert start == "01:00", f"Expected 01:00, got {start}"

    def test_11_00_am_stays_as_11_00(self):
        result = parse_availability("11:00 AM - 12:00 PM")
        assert result is not None
        start, end = result
        assert start == "11:00", f"Expected 11:00, got {start}"

    def test_11_00_pm_converts_to_23_00(self):
        result = parse_availability("11:00 PM - 11:30 PM")
        assert result is not None
        start, end = result
        assert start == "23:00", f"Expected 23:00, got {start}"

    def test_1_00_pm_converts_to_13_00(self):
        result = parse_availability("1:00 PM - 2:00 PM")
        assert result is not None
        start, end = result
        assert start == "13:00", f"Expected 13:00, got {start}"


class TestVariousTimeFormats:

    def test_lowercase_am_pm(self):
        result = parse_availability("9:00 am - 5:00 pm")
        assert result is not None
        start, end = result
        assert start == "09:00"
        assert end == "17:00"

    def test_uppercase_am_pm(self):
        result = parse_availability("9:00 AM - 5:00 PM")
        assert result is not None
        start, end = result
        assert start == "09:00"
        assert end == "17:00"

    def test_mixed_case_am_pm(self):
        result = parse_availability("9:00 Am - 5:00 Pm")
        assert result is not None
        start, end = result
        assert start == "09:00"
        assert end == "17:00"

    def test_no_space_before_am_pm(self):
        result = parse_availability("9:00am - 5:00pm")
        assert result is not None
        start, end = result
        assert start == "09:00"
        assert end == "17:00"

    def test_with_space_before_am_pm(self):
        result = parse_availability("9:00 am - 5:00 pm")
        assert result is not None
        start, end = result
        assert start == "09:00"
        assert end == "17:00"

    def test_dash_without_spaces(self):
        result = parse_availability("9:00am-5:00pm")
        assert result is not None
        start, end = result
        assert start == "09:00"
        assert end == "17:00"

    def test_dash_with_spaces(self):
        result = parse_availability("9:00 am - 5:00 pm")
        assert result is not None
        start, end = result
        assert start == "09:00"
        assert end == "17:00"

    def test_single_digit_hour(self):
        result = parse_availability("8:00 AM - 4:00 PM")
        assert result is not None
        start, end = result
        assert start == "08:00"
        assert end == "16:00"

    def test_double_digit_hour(self):
        result = parse_availability("10:00 AM - 10:00 PM")
        assert result is not None
        start, end = result
        assert start == "10:00"
        assert end == "22:00"


class TestInvalidTimeFormats:

    def test_empty_string_returns_none(self):
        result = parse_availability("")
        assert result is None

    def test_whitespace_only_returns_none(self):
        result = parse_availability("   ")
        assert result is None

    def test_off_returns_none(self):
        result = parse_availability("Off")
        assert result is None

    def test_off_lowercase_returns_none(self):
        result = parse_availability("off")
        assert result is None

    def test_na_returns_none(self):
        result = parse_availability("N/A")
        assert result is None

    def test_na_lowercase_returns_none(self):
        result = parse_availability("n/a")
        assert result is None

    def test_single_time_no_range_returns_none(self):
        result = parse_availability("9:00 AM")
        assert result is None

    def test_invalid_format_returns_none(self):
        result = parse_availability("invalid time")
        assert result is None

    def test_none_input_returns_none(self):
        result = parse_availability(None)
        assert result is None

    def test_multiple_dashes_returns_none(self):
        result = parse_availability("9:00 AM - 12:00 PM - 5:00 PM")
        assert result is None


class TestStandardConversions:

    @pytest.mark.parametrize("input_time,expected_start,expected_end", [
        ("6:00 AM - 7:00 AM", "06:00", "07:00"),
        ("7:00 AM - 8:00 AM", "07:00", "08:00"),
        ("8:00 AM - 9:00 AM", "08:00", "09:00"),
        ("9:00 AM - 10:00 AM", "09:00", "10:00"),
        ("10:00 AM - 11:00 AM", "10:00", "11:00"),
        ("11:00 AM - 12:00 PM", "11:00", "12:00"),
        ("12:00 PM - 1:00 PM", "12:00", "13:00"),
        ("1:00 PM - 2:00 PM", "13:00", "14:00"),
        ("2:00 PM - 3:00 PM", "14:00", "15:00"),
        ("3:00 PM - 4:00 PM", "15:00", "16:00"),
        ("4:00 PM - 5:00 PM", "16:00", "17:00"),
        ("5:00 PM - 6:00 PM", "17:00", "18:00"),
        ("6:00 PM - 7:00 PM", "18:00", "19:00"),
        ("7:00 PM - 8:00 PM", "19:00", "20:00"),
        ("8:00 PM - 9:00 PM", "20:00", "21:00"),
        ("9:00 PM - 10:00 PM", "21:00", "22:00"),
        ("10:00 PM - 11:00 PM", "22:00", "23:00"),
    ])
    def test_am_pm_conversions(self, input_time, expected_start, expected_end):
        result = parse_availability(input_time)
        assert result is not None
        start, end = result
        assert start == expected_start, f"For {input_time}, expected start {expected_start}, got {start}"
        assert end == expected_end, f"For {input_time}, expected end {expected_end}, got {end}"


class TestMidnightEdgeCases:

    def test_midnight_start_12_00_am(self):
        result = parse_availability("12:00 AM - 6:00 AM")
        assert result is not None
        start, end = result
        assert start == "00:00"
        assert end == "06:00"

    def test_midnight_end_12_00_am(self):
        result = parse_availability("10:00 PM - 12:00 AM")
        assert result is not None
        start, end = result
        assert start == "22:00"
        assert end == "00:00"

    def test_noon_start_12_00_pm(self):
        result = parse_availability("12:00 PM - 6:00 PM")
        assert result is not None
        start, end = result
        assert start == "12:00"
        assert end == "18:00"

    def test_noon_end_12_00_pm(self):
        result = parse_availability("9:00 AM - 12:00 PM")
        assert result is not None
        start, end = result
        assert start == "09:00"
        assert end == "12:00"

    def test_12_15_am_converts_correctly(self):
        result = parse_availability("12:15 AM - 1:00 AM")
        assert result is not None
        start, end = result
        assert start == "00:15"

    def test_12_15_pm_stays_as_12_15(self):
        result = parse_availability("12:15 PM - 1:00 PM")
        assert result is not None
        start, end = result
        assert start == "12:15"


class TestParseDateOfBirth:

    def test_iso_format_yyyy_mm_dd(self):
        result = parse_date_of_birth("1995-05-15")
        assert result == date(1995, 5, 15)

    def test_us_format_mm_dd_yyyy(self):
        result = parse_date_of_birth("05/15/1995")
        assert result == date(1995, 5, 15)

    def test_natural_format(self):
        result = parse_date_of_birth("May 15, 1995")
        assert result == date(1995, 5, 15)

    def test_empty_string_returns_none(self):
        result = parse_date_of_birth("")
        assert result is None

    def test_whitespace_only_returns_none(self):
        result = parse_date_of_birth("   ")
        assert result is None

    def test_none_input_returns_none(self):
        result = parse_date_of_birth(None)
        assert result is None

    def test_invalid_date_returns_none(self):
        result = parse_date_of_birth("not a date")
        assert result is None

    def test_numeric_string(self):
        result = parse_date_of_birth("12345")
        assert result is None or isinstance(result, date)


class TestRealWorldScenarios:

    def test_typical_morning_shift(self):
        result = parse_availability("6:00 AM - 2:00 PM")
        assert result is not None
        start, end = result
        assert start == "06:00"
        assert end == "14:00"

    def test_typical_evening_shift(self):
        result = parse_availability("2:00 PM - 10:00 PM")
        assert result is not None
        start, end = result
        assert start == "14:00"
        assert end == "22:00"

    def test_typical_night_shift(self):
        result = parse_availability("10:00 PM - 6:00 AM")
        assert result is not None
        start, end = result
        assert start == "22:00"
        assert end == "06:00"

    def test_full_day_availability(self):
        result = parse_availability("6:00 AM - 11:00 PM")
        assert result is not None
        start, end = result
        assert start == "06:00"
        assert end == "23:00"

    def test_half_hour_increments(self):
        result = parse_availability("9:30 AM - 5:30 PM")
        assert result is not None
        start, end = result
        assert start == "09:30"
        assert end == "17:30"

    def test_retail_hours(self):
        result = parse_availability("9:00 AM - 9:00 PM")
        assert result is not None
        start, end = result
        assert start == "09:00"
        assert end == "21:00"
