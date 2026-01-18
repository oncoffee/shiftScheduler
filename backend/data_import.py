import os
import gspread
from datetime import datetime

try:
    from gspread.exceptions import WorksheetNotFound
except (ImportError, AttributeError):
    WorksheetNotFound = Exception
from pydantic import BaseModel
from dateutil import parser
from dotenv import load_dotenv

load_dotenv()

book_key = os.getenv("GOOGLE_SHEET_KEY")
service_account_path = os.getenv("SERVICE_ACCOUNT_PATH", "service_account.json")

gc = gspread.service_account(service_account_path)
book = gc.open_by_key(book_key)


from datetime import time as time_type
from typing import Any


def fix_column_name(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def pre_row_for_parsing(row: dict[str, Any]) -> dict[str, Any]:
    return {fix_column_name(k): v for k, v in row.items()}


def get_time_periods(start: time_type, end: time_type, interval_in_minutes: int = 30) -> int:
    from datetime import date
    delta = datetime.combine(date.today(), end) - datetime.combine(date.today(), start)
    interval_count = int(delta.total_seconds() / (interval_in_minutes * 60))
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


def load_data() -> dict:
    """Load data from Google Sheets and update module-level cache.

    Returns:
        dict with keys: stores, schedule, employee, config, rates,
        min_hrs_pr_wk, min_hrs, max_hrs
    """
    global stores, schedule, employee, rates, min_hrs_pr_wk, min_hrs, max_hrs, config

    stores = [
        Store.model_validate(pre_row_for_parsing(x))
        for x in book.worksheet("Store").get_all_records()
        if not x.get("Disabled")
    ]

    employee = [
        Employee.model_validate(pre_row_for_parsing(x))
        for x in book.worksheet("Employee").get_all_records()
        if not x.get("Disabled")
    ]

    enabled_employees = {e.employee_name for e in employee}

    schedule = [
        EmployeeSchedule.model_validate(pre_row_for_parsing(x))
        for x in book.worksheet("EmployeeSchedule").get_all_records()
        if not x.get("Disabled") and x.get("Employee name") in enabled_employees
    ]

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

    return {
        "stores": stores,
        "schedule": schedule,
        "employee": employee,
        "config": config,
        "rates": rates,
        "min_hrs_pr_wk": min_hrs_pr_wk,
        "min_hrs": min_hrs,
        "max_hrs": max_hrs,
    }


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


