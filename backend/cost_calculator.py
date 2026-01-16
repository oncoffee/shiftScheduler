from datetime import datetime
from typing import Optional
from schemas import (
    EmployeeDaySchedule,
    DayScheduleSummary,
    WeeklyScheduleResult,
    UnfilledPeriod,
)
from db import EmployeeDoc, ConfigDoc


def parse_time_to_minutes(time_str: str) -> int:
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def get_minimum_workers(
    day_of_week: str,
    staffing_requirements: list[dict] | None = None,
    store_start_minutes: int = 6 * 60,
    store_end_minutes: int = 24 * 60,
    default_min: int = 2
) -> list[int]:
    if staffing_requirements is None:
        if day_of_week in ("Saturday", "Sunday"):
            return [2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 3, 3, 3, 3, 3, 3, 2, 2]
        return [2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 3, 3, 3, 3, 3, 3, 2, 2]

    day_type = "weekend" if day_of_week in ("Saturday", "Sunday") else "weekday"
    relevant_reqs = [r for r in staffing_requirements if r.get("day_type") == day_type]

    num_periods = (store_end_minutes - store_start_minutes) // 30
    minimum_workers = []

    for period_idx in range(num_periods):
        period_start = store_start_minutes + (period_idx * 30)

        min_staff = default_min
        for req in relevant_reqs:
            req_start = parse_time_to_minutes(req["start_time"])
            req_end = parse_time_to_minutes(req["end_time"])
            if req_start <= period_start < req_end:
                min_staff = req["min_staff"]
                break

        minimum_workers.append(min_staff)

    return minimum_workers


async def get_employee_hourly_rate(employee_name: str) -> float:
    employee = await EmployeeDoc.find_one(EmployeeDoc.employee_name == employee_name)
    if employee:
        return employee.hourly_rate
    return 15.0


async def get_config() -> dict:
    config = await ConfigDoc.find_one()
    if config:
        return {
            "dummy_worker_cost": config.dummy_worker_cost,
            "short_shift_penalty": config.short_shift_penalty,
            "min_shift_hours": config.min_shift_hours,
            "max_daily_hours": config.max_daily_hours,
        }
    return {
        "dummy_worker_cost": 100.0,
        "short_shift_penalty": 50.0,
        "min_shift_hours": 3.0,
        "max_daily_hours": 11.0,
    }


async def calculate_day_cost(
    day_schedules: list[EmployeeDaySchedule],
    day_of_week: str,
    staffing_requirements: list[dict] | None = None,
) -> tuple[float, float, float, list[UnfilledPeriod]]:
    config = await get_config()
    minimum_workers = get_minimum_workers(day_of_week, staffing_requirements)

    labor_cost = 0.0
    short_shift_penalty = 0.0

    for schedule in day_schedules:
        if schedule.total_hours > 0:
            rate = await get_employee_hourly_rate(schedule.employee_name)
            labor_cost += rate * schedule.total_hours

            if schedule.total_hours < config["min_shift_hours"]:
                penalty_hours = config["min_shift_hours"] - schedule.total_hours
                short_shift_penalty += penalty_hours * config["short_shift_penalty"]

    period_counts: dict[int, int] = {}

    for schedule in day_schedules:
        for period in schedule.periods:
            if period.scheduled:
                period_counts[period.period_index] = period_counts.get(period.period_index, 0) + 1

    unfilled_periods = []
    dummy_cost = 0.0

    for period_idx, min_required in enumerate(minimum_workers):
        if period_idx >= len(minimum_workers):
            break
        actual_workers = period_counts.get(period_idx, 0)
        if actual_workers < min_required:
            workers_needed = min_required - actual_workers
            dummy_cost += workers_needed * config["dummy_worker_cost"]

            start_time = None
            end_time = None
            for schedule in day_schedules:
                for period in schedule.periods:
                    if period.period_index == period_idx:
                        start_time = period.start_time
                        end_time = period.end_time
                        break
                if start_time:
                    break

            if start_time and end_time:
                unfilled_periods.append(UnfilledPeriod(
                    period_index=period_idx,
                    start_time=start_time,
                    end_time=end_time,
                    workers_needed=workers_needed,
                ))

    total_cost = labor_cost + dummy_cost + short_shift_penalty

    return total_cost, labor_cost, dummy_cost, short_shift_penalty, unfilled_periods


async def recalculate_schedule_costs(
    schedules: list[EmployeeDaySchedule],
    daily_summaries: list[DayScheduleSummary],
    staffing_requirements: list[dict] | None = None,
) -> tuple[list[DayScheduleSummary], float, float, float]:
    updated_summaries = []
    total_weekly_cost = 0.0
    total_dummy_cost = 0.0
    total_short_shift_penalty = 0.0

    schedules_by_day: dict[str, list[EmployeeDaySchedule]] = {}
    for schedule in schedules:
        day = schedule.day_of_week
        if day not in schedules_by_day:
            schedules_by_day[day] = []
        schedules_by_day[day].append(schedule)

    for summary in daily_summaries:
        day = summary.day_of_week
        day_schedules = schedules_by_day.get(day, [])

        total_cost, labor_cost, dummy_cost, short_shift_penalty, unfilled = await calculate_day_cost(
            day_schedules, day, staffing_requirements
        )

        employees_scheduled = sum(1 for s in day_schedules if s.total_hours > 0)
        total_labor_hours = sum(s.total_hours for s in day_schedules)

        updated_summaries.append(DayScheduleSummary(
            day_of_week=day,
            total_cost=total_cost,
            employees_scheduled=employees_scheduled,
            total_labor_hours=total_labor_hours,
            dummy_worker_cost=dummy_cost,
            unfilled_periods=unfilled,
        ))

        total_weekly_cost += total_cost
        total_dummy_cost += dummy_cost
        total_short_shift_penalty += short_shift_penalty

    return updated_summaries, total_weekly_cost, total_dummy_cost, total_short_shift_penalty


class ValidationError:
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message

    def to_dict(self):
        return {"code": self.code, "message": self.message}


class ValidationWarning:
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message

    def to_dict(self):
        return {"code": self.code, "message": self.message}


async def validate_schedule_change(
    employee_name: str,
    day_of_week: str,
    proposed_start: str,
    proposed_end: str,
    current_schedules: list[EmployeeDaySchedule],
    exclude_original: bool = True,
    skip_availability_check: bool = False,
) -> tuple[bool, list[ValidationError], list[ValidationWarning]]:
    errors = []
    warnings = []
    config = await get_config()

    start_minutes = parse_time_to_minutes(proposed_start)
    end_minutes = parse_time_to_minutes(proposed_end)

    if start_minutes >= end_minutes:
        errors.append(ValidationError(
            "INVALID_TIME_RANGE",
            "Start time must be before end time"
        ))
        return False, errors, warnings

    shift_hours = (end_minutes - start_minutes) / 60

    if shift_hours < 0.5:
        errors.append(ValidationError(
            "SHIFT_TOO_SHORT",
            "Shift must be at least 30 minutes"
        ))
        return False, errors, warnings

    if shift_hours > config["max_daily_hours"]:
        errors.append(ValidationError(
            "EXCEEDS_MAX_HOURS",
            f"Shift exceeds maximum daily hours ({config['max_daily_hours']}h)"
        ))
        return False, errors, warnings

    if not skip_availability_check:
        employee = await EmployeeDoc.find_one(EmployeeDoc.employee_name == employee_name)
        if employee:
            day_availability = None
            for avail in employee.availability:
                if avail.day_of_week == day_of_week:
                    day_availability = avail
                    break

            if day_availability:
                avail_start = parse_time_to_minutes(day_availability.start_time)
                avail_end = parse_time_to_minutes(day_availability.end_time)

                if start_minutes < avail_start or end_minutes > avail_end:
                    errors.append(ValidationError(
                        "OUTSIDE_AVAILABILITY",
                        f"Shift is outside employee availability ({day_availability.start_time} - {day_availability.end_time})"
                    ))
                    return False, errors, warnings
            else:
                errors.append(ValidationError(
                    "NO_AVAILABILITY",
                    f"Employee has no availability on {day_of_week}"
                ))
                return False, errors, warnings

    if shift_hours < config["min_shift_hours"]:
        warnings.append(ValidationWarning(
            "SHORT_SHIFT",
            f"Shift is shorter than minimum ({config['min_shift_hours']}h) - penalty will apply"
        ))

    return True, errors, warnings


def update_assignment_times(
    schedule: EmployeeDaySchedule,
    new_start: str,
    new_end: str,
    config: dict,
) -> EmployeeDaySchedule:
    start_minutes = parse_time_to_minutes(new_start)
    end_minutes = parse_time_to_minutes(new_end)

    updated_periods = []
    for period in schedule.periods:
        period_start = parse_time_to_minutes(period.start_time)
        period_end = parse_time_to_minutes(period.end_time)

        scheduled = period_start >= start_minutes and period_end <= end_minutes

        updated_periods.append(type(period)(
            period_index=period.period_index,
            start_time=period.start_time,
            end_time=period.end_time,
            scheduled=scheduled,
        ))

    scheduled_count = sum(1 for p in updated_periods if p.scheduled)
    total_hours = scheduled_count * 0.5

    is_short_shift = total_hours > 0 and total_hours < config["min_shift_hours"]

    return EmployeeDaySchedule(
        employee_name=schedule.employee_name,
        day_of_week=schedule.day_of_week,
        periods=updated_periods,
        total_hours=total_hours,
        shift_start=new_start if total_hours > 0 else None,
        shift_end=new_end if total_hours > 0 else None,
        is_short_shift=is_short_shift,
    )
