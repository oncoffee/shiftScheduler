import gspread
from datetime import datetime
from pydantic import BaseModel
from dateutil import parser
from pprint import pprint

book_key = '1QOCmyAmXD85Cp4tOuDSE26oLmQF3k9AmTRux1CfSbqc'

gc = gspread.service_account("/home/swap/PycharmProjects/service_account.json")
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


stores: list[Store] = [
    Store.parse_obj(pre_row_for_parsing(x))
    for x in book.worksheet("Store").get_all_records()
    if not x.get("Disabled")
]

# print("\nStores:")
# pprint(stores)

for s in stores:
    store_name = s.store_name
    day_of_week = s.day_of_week
    start_time = parser.parse(s.start_time).time()
    end_time = parser.parse(s.end_time).time()

print(store_name)
print(day_of_week)
print(start_time)
print(end_time)
