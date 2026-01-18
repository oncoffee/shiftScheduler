import os
import gspread
from datetime import datetime

try:
    from gspread.exceptions import WorksheetNotFound
except (ImportError, AttributeError):
    WorksheetNotFound = Exception
from pydantic import BaseModel
from dateutil import parser
from pprint import pprint
from dotenv import load_dotenv

load_dotenv()

book_key = os.getenv("GOOGLE_SHEET_KEY")
service_account_path = os.getenv("SERVICE_ACCOUNT_PATH", "service_account.json")

gc = gspread.service_account(service_account_path)
book = gc.open_by_key(book_key)


def fix_column_name(name: str):
    return name.strip().lower().replace(" ", "_")


def pre_row_for_parsing(row: dict):
    return {fix_column_name(k): v for k, v in row.items()}


def get_time_periods(start, end, interval_in_minutes=30):
    interval = interval_in_minutes
    delta = datetime.datetime.combine(datetime.date.today(), end) - \
            datetime.datetime.combine(datetime.date.today(), start)
    interval_count = int(delta.total_seconds() / interval.total_seconds())
    return interval_count


class Store(BaseModel):
    week_no: int
    store_name: str
    day_of_week: str
    start_time: str
    end_time: str


class EmployeeSchedule(BaseModel):
    employee_name: str
    day_of_week: str
    availability: str

class Employee(BaseModel):
    employee_name: str
    hourly_rate: float
    minimum_hours_per_week: int
    minimum_hours: int
    maximum_hours: int


class Config(BaseModel):
    dummy_worker_cost: float = 100.0  # Cost per period for unfilled shifts
    short_shift_penalty: float = 50.0  # Penalty per hour below minimum
    min_shift_hours: float = 3.0  # Minimum shift length in hours
    max_daily_hours: float = 11.0  # Maximum hours per employee per day
    solver_type: str = "gurobi"


def load_data():
    """Load data from Google Sheets. Call this to refresh data."""
    global stores, schedule, employee, rates, min_hrs_pr_wk, min_hrs, max_hrs, config

    stores = [
        Store.parse_obj(pre_row_for_parsing(x))
        for x in book.worksheet("Store").get_all_records()
        if not x.get("Disabled")
    ]

    # Load enabled employees first
    employee = [
        Employee.parse_obj(pre_row_for_parsing(x))
        for x in book.worksheet("Employee").get_all_records()
        if not x.get("Disabled")
    ]

    # Get set of enabled employee names
    enabled_employees = {e.employee_name for e in employee}

    # Filter schedule to only include enabled employees
    schedule = [
        EmployeeSchedule.parse_obj(pre_row_for_parsing(x))
        for x in book.worksheet("EmployeeSchedule").get_all_records()
        if not x.get("Disabled") and x.get("Employee name") in enabled_employees
    ]

    # Load config from Config tab
    try:
        config_rows = book.worksheet("Config").get_all_records()
        config_dict = {row.get("Setting"): row.get("Value") for row in config_rows if row.get("Setting")}
        config = Config(
            dummy_worker_cost=float(config_dict.get("dummy_worker_cost", 100)),
            short_shift_penalty=float(config_dict.get("short_shift_penalty", 50)),
            min_shift_hours=float(config_dict.get("min_shift_hours", 3)),
            max_daily_hours=float(config_dict.get("max_daily_hours", 11)),
        )
    except (WorksheetNotFound, KeyError, ValueError):
        config = Config()

    rates = {}
    min_hrs_pr_wk = {}
    min_hrs = {}
    max_hrs = {}

    for e in employee:
        rates[e.employee_name] = e.hourly_rate
        min_hrs_pr_wk[e.employee_name] = e.minimum_hours_per_week
        min_hrs[e.employee_name] = e.minimum_hours
        max_hrs[e.employee_name] = e.maximum_hours


# Initialize on import
stores: list[Store] = []
schedule: list[EmployeeSchedule] = []
employee: list[Employee] = []
config: Config = Config()
rates = {}
min_hrs_pr_wk = {}
min_hrs = {}
max_hrs = {}

# Load initial data
load_data()


