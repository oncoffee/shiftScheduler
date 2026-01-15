import os
import gspread
from datetime import datetime
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


stores: list[Store] = [
    Store.parse_obj(pre_row_for_parsing(x))
    for x in book.worksheet("Store").get_all_records()
    if not x.get("Disabled")
]

schedule: list[EmployeeSchedule] = [
    EmployeeSchedule.parse_obj(pre_row_for_parsing(x))
    for x in book.worksheet("EmployeeSchedule").get_all_records()
    if not x.get("Disabled")
]

employee: list[Employee] =[
    Employee.parse_obj(pre_row_for_parsing(x))
    for x in book.worksheet("Employee").get_all_records()
    if not x.get("Disabled")
]

# print("\nStores:")
# pprint(stores)

rates = {}
min_hrs_pr_wk = {}
min_hrs = {}
max_hrs = {}

for e in employee:
    rates[e.employee_name] = e.hourly_rate
    min_hrs_pr_wk[e.employee_name] = e.minimum_hours_per_week
    min_hrs[e.employee_name] = e.minimum_hours
    max_hrs[e.employee_name] = e.maximum_hours


