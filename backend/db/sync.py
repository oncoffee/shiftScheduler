from datetime import datetime, date
from dateutil import parser as date_parser
import data_import
from .models import (
    EmployeeDoc,
    StoreDoc,
    ConfigDoc,
    AvailabilitySlot,
    StoreHours,
)


def parse_date_of_birth(dob_str: str) -> date | None:
    """
    Parse date of birth from various formats.
    Supports: YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY, "May 15, 1995", etc.
    """
    if not dob_str or not str(dob_str).strip():
        return None

    dob_str = str(dob_str).strip()

    try:
        # Use dateutil parser for flexible parsing
        parsed = date_parser.parse(dob_str, dayfirst=False)
        return parsed.date()
    except (ValueError, TypeError):
        return None


def parse_availability(availability_str: str) -> tuple[str, str] | None:
    if not availability_str or availability_str.lower().strip() in ("off", "n/a", ""):
        return None

    try:
        if " - " in availability_str:
            parts = availability_str.split(" - ")
        else:
            parts = availability_str.replace(" ", "").split("-")

        if len(parts) != 2:
            return None

        def convert_time(t: str) -> str:
            t = t.strip().lower()

            is_pm = "pm" in t
            is_am = "am" in t
            t = t.replace("pm", "").replace("am", "").strip()

            time_parts = t.split(":")
            hour = int(time_parts[0])
            minute = time_parts[1] if len(time_parts) > 1 else "00"

            if len(minute) > 2 or not minute.isdigit():
                minute = minute[:2]

            if is_pm and hour != 12:
                hour += 12
            elif is_am and hour == 12:
                hour = 0

            return f"{hour:02d}:{minute}"

        start = convert_time(parts[0])
        end = convert_time(parts[1])
        return start, end
    except Exception:
        return None


async def sync_employees() -> int:
    data_import.load_data()

    employee_records = data_import.book.worksheet("Employee").get_all_records()
    schedule_records = data_import.book.worksheet("EmployeeSchedule").get_all_records()

    availability_map: dict[str, list[AvailabilitySlot]] = {}
    for row in schedule_records:
        emp_name = row.get("Employee name")
        day = row.get("Day of week")
        avail_str = row.get("Availability", "")
        disabled = row.get("Disabled", False)

        if disabled or not emp_name:
            continue

        parsed = parse_availability(avail_str)
        if parsed:
            start, end = parsed
            if emp_name not in availability_map:
                availability_map[emp_name] = []
            availability_map[emp_name].append(
                AvailabilitySlot(day_of_week=day, start_time=start, end_time=end)
            )

    count = 0
    for row in employee_records:
        emp_name = row.get("Employee name")
        if not emp_name:
            continue

        disabled = bool(row.get("Disabled", False))

        # Parse date of birth from Google Sheets
        dob_str = row.get("Date of Birth", "") or row.get("DOB", "") or row.get("Birth Date", "")
        date_of_birth = parse_date_of_birth(dob_str)

        existing = await EmployeeDoc.find_one(EmployeeDoc.employee_name == emp_name)

        employee_data = {
            "employee_name": emp_name,
            "hourly_rate": float(row.get("Hourly rate", 0)),
            "minimum_hours_per_week": int(row.get("Minimum hours per week", 0)),
            "minimum_hours": int(row.get("Minimum hours", 0)),
            "maximum_hours": int(row.get("Maximum hours", 11)),
            "disabled": disabled,
            "availability": availability_map.get(emp_name, []),
            "date_of_birth": date_of_birth,
            "updated_at": datetime.utcnow(),
        }

        if existing:
            await existing.set(employee_data)
        else:
            employee_data["created_at"] = datetime.utcnow()
            await EmployeeDoc(**employee_data).insert()

        count += 1

    return count


async def sync_stores() -> int:
    data_import.load_data()

    store_records = data_import.book.worksheet("Store").get_all_records()

    hours_map: dict[str, list[StoreHours]] = {}
    for row in store_records:
        store_name = row.get("Store name")
        disabled = row.get("Disabled", False)

        if disabled or not store_name:
            continue

        if store_name not in hours_map:
            hours_map[store_name] = []

        hours_map[store_name].append(
            StoreHours(
                day_of_week=row.get("Day of week", ""),
                start_time=row.get("Start time", ""),
                end_time=row.get("End time", ""),
            )
        )

    count = 0
    for store_name, hours in hours_map.items():
        existing = await StoreDoc.find_one(StoreDoc.store_name == store_name)

        store_data = {
            "store_name": store_name,
            "hours": hours,
            "updated_at": datetime.utcnow(),
        }

        if existing:
            await existing.set(store_data)
        else:
            store_data["created_at"] = datetime.utcnow()
            await StoreDoc(**store_data).insert()

        count += 1

    return count


async def sync_config() -> bool:
    data_import.load_data()
    config = data_import.config

    existing = await ConfigDoc.find_one()

    config_data = {
        "dummy_worker_cost": config.dummy_worker_cost,
        "short_shift_penalty": config.short_shift_penalty,
        "min_shift_hours": config.min_shift_hours,
        "max_daily_hours": config.max_daily_hours,
        "updated_at": datetime.utcnow(),
    }

    if existing:
        await existing.set(config_data)
    else:
        await ConfigDoc(**config_data).insert()

    return True


async def sync_all_from_sheets() -> dict:
    employees_count = await sync_employees()
    stores_count = await sync_stores()
    config_synced = await sync_config()

    return {
        "employees_synced": employees_count,
        "stores_synced": stores_count,
        "config_synced": config_synced,
        "synced_at": datetime.utcnow().isoformat(),
    }
