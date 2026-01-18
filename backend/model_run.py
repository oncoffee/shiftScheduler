from data_manipulation import putting_store_time_in_df, creating_employee_df
from dateutil import parser
import data_import
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta, date as date_type
from typing import Optional

from schemas import (
    ShiftPeriod,
    EmployeeDaySchedule,
    DayScheduleSummary,
    WeeklyScheduleResult,
    UnfilledPeriod,
)
from solvers import (
    create_solver,
    SolverType,
    SolverConfig,
    ScheduleProblem,
    SolverStatus,
)
from compliance.engine import apply_minor_availability_filter, apply_rest_constraints


DAY_OF_WEEK_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

DEFAULT_STAFFING_WEEKEND = [2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 3, 3, 3, 3, 3, 3, 2, 2]
DEFAULT_STAFFING_WEEKDAY = [2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 3, 3, 3, 3, 3, 3, 2, 2]
PERIOD_DURATION_MINUTES = 30
MINOR_AGE_THRESHOLD = 18


def get_employee_minor_status_sync(minor_age_threshold: int = MINOR_AGE_THRESHOLD) -> dict[str, bool]:
    """
    Synchronously get minor status for all employees.
    Falls back to checking data_import if database is unavailable.

    Args:
        minor_age_threshold: Age below which an employee is considered a minor.
                            This varies by jurisdiction (default 18 for federal).
    """
    # Try to get from cached data_import first (loaded from DB via sync)
    minor_status = {}
    for emp in data_import.employee:
        # Check if employee has is_minor attribute (manual override)
        is_minor = getattr(emp, 'is_minor', False)
        date_of_birth = getattr(emp, 'date_of_birth', None)

        # Auto-calculate from DOB if available using jurisdiction's threshold
        if date_of_birth and not is_minor:
            today = date_type.today()
            age = today.year - date_of_birth.year
            if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
                age -= 1
            is_minor = age < minor_age_threshold

        minor_status[emp.employee_name] = is_minor

    return minor_status


def get_default_compliance_rules() -> dict:
    """
    Get default federal compliance rules.
    Used as fallback when no jurisdiction-specific rules are provided.
    """
    return {
        "min_rest_hours": 8.0,
        "minor_curfew_end": "22:00",
        "minor_earliest_start": "06:00",
        "minor_max_daily_hours": 8.0,
        "minor_max_weekly_hours": 40.0,
        "minor_age_threshold": 18,
        "daily_overtime_threshold": None,
        "weekly_overtime_threshold": 40.0,
        "meal_break_after_hours": 5.0,
        "meal_break_duration_minutes": 30,
    }


def filter_availability_for_compliance(
    employee_availability: dict[str, list[int]],
    time_periods: list[str],
    employees: list[str],
    minor_status: dict[str, bool],
    compliance_rules: dict,
    store_start_time,
) -> tuple[dict[str, list[int]], dict[str, bool], int | None, int | None]:
    """
    Apply compliance filters to employee availability.

    Returns:
        - filtered_availability: availability with minor restrictions applied
        - employee_is_minor: map of employee -> is_minor
        - minor_curfew_period: period index where curfew starts
        - minor_earliest_period: period index where minors can start
    """
    # Build employee_is_minor map for the employees in this day
    employee_is_minor = {emp: minor_status.get(emp, False) for emp in employees}

    # Convert store start time to period time strings
    period_times = []
    for idx, t in enumerate(time_periods):
        # time_periods can be integers (period indices) or strings
        # We need to convert to actual times like "08:00", "08:30", etc.
        if isinstance(t, int):
            period_idx = t
        elif isinstance(t, str) and t.isdigit():
            period_idx = int(t)
        else:
            # t is already a time string or we use the index
            period_idx = idx
        base = datetime.combine(datetime.today(), store_start_time)
        result = base + timedelta(minutes=30 * period_idx)
        period_times.append(result.strftime("%H:%M"))

    # Apply minor availability filter
    filtered_availability, curfew_period, earliest_period = apply_minor_availability_filter(
        employee_availability=employee_availability,
        employee_is_minor=employee_is_minor,
        time_periods=period_times,
        curfew_time=compliance_rules.get("minor_curfew_end", "22:00"),
        earliest_time=compliance_rules.get("minor_earliest_start", "06:00"),
    )

    return filtered_availability, employee_is_minor, curfew_period, earliest_period


def get_week_dates(start_date: date_type) -> dict[str, date_type]:
    """Return {day_of_week: actual_date} for the week containing start_date.
    Aligns to Monday as the start of the week."""
    days_since_monday = start_date.weekday()  # Monday = 0
    monday = start_date - timedelta(days=days_since_monday)
    return {
        "Monday": monday,
        "Tuesday": monday + timedelta(days=1),
        "Wednesday": monday + timedelta(days=2),
        "Thursday": monday + timedelta(days=3),
        "Friday": monday + timedelta(days=4),
        "Saturday": monday + timedelta(days=5),
        "Sunday": monday + timedelta(days=6),
    }


def period_to_time(store_start_time, period_index: int) -> str:
    """Convert period index to time string (HH:MM)"""
    base = datetime.combine(datetime.today(), store_start_time)
    result = base + timedelta(minutes=30 * period_index)
    return result.strftime("%H:%M")


def convert_schedule_to_structured(
    df_wide: pd.DataFrame,
    day_of_week: str,
    store_start_time,
    cost: float,
    unfilled_periods: list[UnfilledPeriod] = None,
    dummy_worker_cost: float = 0,
    min_shift_hours: float = 3.0,
    actual_date: str | None = None,
    break_periods: dict[str, list[int]] | None = None,
) -> tuple[list[EmployeeDaySchedule], DayScheduleSummary]:
    """Convert pivot table to structured schedule data"""
    employee_schedules = []
    break_periods = break_periods or {}

    for employee in df_wide.index:
        periods = []
        scheduled_periods = []
        emp_break_periods = set(break_periods.get(employee, []))

        for period_idx, col in enumerate(df_wide.columns):
            start_time = period_to_time(store_start_time, period_idx)
            end_time = period_to_time(store_start_time, period_idx + 1)
            scheduled = df_wide.loc[employee, col] == "*"
            is_break = period_idx in emp_break_periods

            period = ShiftPeriod(
                period_index=period_idx,
                start_time=start_time,
                end_time=end_time,
                scheduled=scheduled,
                is_break=is_break,
            )
            periods.append(period)

            if scheduled:
                scheduled_periods.append(period)

        total_hours = len(scheduled_periods) * 0.5
        shift_start = scheduled_periods[0].start_time if scheduled_periods else None
        shift_end = scheduled_periods[-1].end_time if scheduled_periods else None
        is_short_shift = total_hours > 0 and total_hours < min_shift_hours

        employee_schedules.append(
            EmployeeDaySchedule(
                employee_name=employee,
                day_of_week=day_of_week,
                date=actual_date,
                periods=periods,
                total_hours=total_hours,
                shift_start=shift_start,
                shift_end=shift_end,
                is_short_shift=is_short_shift,
            )
        )

    employees_scheduled = sum(1 for s in employee_schedules if s.total_hours > 0)
    total_labor_hours = sum(s.total_hours for s in employee_schedules)

    summary = DayScheduleSummary(
        day_of_week=day_of_week,
        date=actual_date,
        total_cost=cost,
        employees_scheduled=employees_scheduled,
        total_labor_hours=total_labor_hours,
        unfilled_periods=unfilled_periods or [],
        dummy_worker_cost=dummy_worker_cost,
    )

    return employee_schedules, summary


_logging_configured = False


def setup_logging():
    global _logging_configured
    if _logging_configured:
        return

    logger = logging.getLogger()
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s'))
        logger.addHandler(console)

    _logging_configured = True


def time_to_minutes(time_str: str) -> int:
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def get_minimum_workers(
    day_of_week: str,
    store_start_time,
    store_end_time,
    staffing_requirements: list[dict] | None = None,
    default_min: int = 2
) -> list[int]:
    if staffing_requirements is None:
        if day_of_week in ('Saturday', 'Sunday'):
            return DEFAULT_STAFFING_WEEKEND.copy()
        return DEFAULT_STAFFING_WEEKDAY.copy()

    day_type = "weekend" if day_of_week in ('Saturday', 'Sunday') else "weekday"
    relevant_reqs = [r for r in staffing_requirements if r.get("day_type") == day_type]

    store_start_mins = store_start_time.hour * 60 + store_start_time.minute
    store_end_mins = store_end_time.hour * 60 + store_end_time.minute
    if store_end_mins <= store_start_mins:
        store_end_mins = 24 * 60

    num_periods = (store_end_mins - store_start_mins) // PERIOD_DURATION_MINUTES
    minimum_workers = []

    for period_idx in range(num_periods):
        period_start = store_start_mins + (period_idx * PERIOD_DURATION_MINUTES)
        period_end = period_start + PERIOD_DURATION_MINUTES

        min_staff = default_min
        for req in relevant_reqs:
            req_start = time_to_minutes(req["start_time"])
            req_end = time_to_minutes(req["end_time"])
            if req_start <= period_start < req_end:
                min_staff = req["min_staff"]
                break

        minimum_workers.append(min_staff)

    return minimum_workers


def extract_schedule_dataframe_from_result(
    result,
    employees: list[str],
    time_periods: list[str],
) -> pd.DataFrame:
    """Convert solver result to pivot table DataFrame."""
    data = []
    for b in employees:
        for t in time_periods:
            scheduled_val = result.schedule_matrix.get((b, t), 0)
            data.append({
                "employee": b,
                "period": t,
                "status": "*" if scheduled_val == 1 else "-",
            })
    df = pd.DataFrame(data)
    df_wide = pd.pivot(df, index="employee", columns="period", values="status")
    return df_wide[time_periods]


def main(
    start_date: date_type,
    end_date: date_type,
    locked_shifts: list[dict] | None = None,
    staffing_requirements: list[dict] | None = None,
    solver_type: str = "gurobi",
    enable_compliance_filter: bool = True,
    compliance_rules: dict | None = None,
) -> WeeklyScheduleResult:
    """
    Run the shift scheduling solver.

    Args:
        start_date: Start date for the schedule
        end_date: End date for the schedule
        locked_shifts: Shifts that should not be changed
        staffing_requirements: Minimum staffing requirements per time block
        solver_type: Which solver to use ("gurobi", "pulp", "ortools")
        enable_compliance_filter: Whether to apply compliance rules
        compliance_rules: Jurisdiction-specific compliance rules (from ComplianceRuleDoc).
                         If None, uses default federal rules.
    """
    data_import.load_data()
    setup_logging()

    hourly_rates = data_import.rates
    maximum_periods = int(data_import.config.max_daily_hours * 2)

    employee_min_hrs = data_import.min_hrs_pr_wk

    # Get compliance data - use passed rules or fall back to defaults
    if compliance_rules is None:
        compliance_rules = get_default_compliance_rules() if enable_compliance_filter else {}

    # Use jurisdiction's minor age threshold (default 18)
    minor_age_threshold = compliance_rules.get("minor_age_threshold", 18) if compliance_rules else 18
    minor_status = get_employee_minor_status_sync(minor_age_threshold) if enable_compliance_filter else {}

    all_schedules: list[EmployeeDaySchedule] = []
    daily_summaries: list[DayScheduleSummary] = []
    total_weekly_cost = 0.0
    total_dummy_cost = 0.0
    total_short_shift_cost = 0.0
    store_name = ""

    # Track previous day's end times for rest-between-shifts compliance
    previous_day_end_times: dict[str, str] = {}  # employee -> "HH:MM"

    # Build a map of day_of_week -> store data for quick lookup
    store_by_day = {}
    for s in data_import.stores:
        store_name = s.store_name  # Capture store name
        store_by_day[s.day_of_week] = s

    # Iterate through each date in the range
    current_date = start_date
    while current_date <= end_date:
        day_of_week = DAY_OF_WEEK_ORDER[current_date.weekday()]
        actual_date_str = current_date.isoformat()

        # Check if we have store data for this day
        s = store_by_day.get(day_of_week)
        if not s:
            current_date += timedelta(days=1)
            continue

        store_start_time = parser.parse(s.start_time).time()
        store_end_time = parser.parse(s.end_time).time()

        minimum_workers = get_minimum_workers(
            day_of_week,
            store_start_time,
            store_end_time,
            staffing_requirements
        )

        store_df = putting_store_time_in_df(s.day_of_week, store_start_time,
                                            store_end_time)

        for sch in data_import.schedule:
            if sch.day_of_week == s.day_of_week:
                df_name = f'df_{sch.employee_name.lower()}'
                df = creating_employee_df(sch.employee_name, sch.day_of_week,
                                          sch.availability.split(" - ")[0],
                                          sch.availability.split(" - ")[1])
                locals()[df_name] = df
                store_df = store_df.merge(
                    df,
                    on=['day_of_week', 'Time'],
                    how='left'
                )
            store_df = store_df.replace(np.nan, 0)

        employees = [x for x in store_df.columns][3:]
        timePeriods = [x for x in store_df.Period]
        T = len(timePeriods)
        B = len(employees)

        employee_availability = {col: store_df[col].tolist()
                                 for col in store_df[[emp for emp in employees]].columns}

        # Apply compliance filtering for minors
        employee_is_minor = {}
        minor_curfew_period = None
        minor_earliest_period = None

        if enable_compliance_filter and minor_status:
            (
                employee_availability,
                employee_is_minor,
                minor_curfew_period,
                minor_earliest_period,
            ) = filter_availability_for_compliance(
                employee_availability=employee_availability,
                time_periods=timePeriods,
                employees=employees,
                minor_status=minor_status,
                compliance_rules=compliance_rules,
                store_start_time=store_start_time,
            )

            # Log minor employees affected
            minors_today = [emp for emp in employees if employee_is_minor.get(emp, False)]
            if minors_today:
                logging.info(f"Minor employees on {day_of_week}: {minors_today}")
                if minor_curfew_period:
                    logging.info(f"Minor curfew starts at period {minor_curfew_period}")

        # Apply rest-between-shifts constraints
        rest_blocked_periods: dict[str, set[int]] = {}
        if enable_compliance_filter and previous_day_end_times:
            min_rest_hours = compliance_rules.get("min_rest_hours", 8.0)

            # Build time period strings for rest constraint calculation
            period_times = []
            for t_idx in range(len(timePeriods)):
                base = datetime.combine(datetime.today(), store_start_time)
                period_time = base + timedelta(minutes=30 * t_idx)
                period_times.append(period_time.strftime("%H:%M"))

            rest_blocked_periods = apply_rest_constraints(
                employee_availability=employee_availability,
                previous_day_end_times=previous_day_end_times,
                time_periods=period_times,
                min_rest_hours=min_rest_hours,
                store_open_time=store_start_time.strftime("%H:%M"),
            )

            # Apply rest blocks to availability
            if rest_blocked_periods:
                for emp, blocked in rest_blocked_periods.items():
                    if emp in employee_availability:
                        # Zero out blocked periods
                        avail = employee_availability[emp]
                        for period_idx in blocked:
                            if period_idx < len(avail):
                                avail[period_idx] = 0
                        logging.info(f"Rest constraint: {emp} blocked for periods {sorted(blocked)} (min {min_rest_hours}h rest)")

        DUMMY_WORKER_COST = data_import.config.dummy_worker_cost
        SHORT_SHIFT_PENALTY = data_import.config.short_shift_penalty

        locked_periods_set = set()
        if locked_shifts:
            for locked in locked_shifts:
                if locked.get("date") == actual_date_str:
                    emp = locked["employee_name"]
                    if emp in employees:
                        for period_idx in locked["periods"]:
                            if period_idx < len(timePeriods):
                                locked_periods_set.add((emp, period_idx))
                        logging.info(f"Locked shift for {emp} on {actual_date_str}: periods {locked['periods']}")

        # Get meal break settings from compliance rules
        meal_break_enabled = compliance_rules.get("meal_break_enabled", True) if compliance_rules else True
        meal_break_threshold = compliance_rules.get("meal_break_after_hours", 5.0) if compliance_rules else 5.0

        solver_config = SolverConfig(
            dummy_worker_cost=DUMMY_WORKER_COST,
            short_shift_penalty=SHORT_SHIFT_PENALTY,
            min_shift_hours=data_import.config.min_shift_hours,
            max_daily_hours=data_import.config.max_daily_hours,
            meal_break_enabled=meal_break_enabled,
            meal_break_threshold_hours=meal_break_threshold,
            meal_break_duration_periods=1,  # 30 minutes (1 period)
        )

        problem = ScheduleProblem(
            employees=employees,
            time_periods=timePeriods,
            employee_availability=employee_availability,
            hourly_rates=hourly_rates,
            minimum_workers=minimum_workers,
            locked_periods=locked_periods_set,
            employee_is_minor=employee_is_minor,
            minor_curfew_period=minor_curfew_period,
            minor_earliest_period=minor_earliest_period,
        )

        solver = create_solver(solver_type)
        result = solver.solve(problem, solver_config)
        solver.write_model("scheduler.lp")

        if result.status == SolverStatus.INFEASIBLE:
            logging.error(f"Model infeasible for {day_of_week}. Computing IIS...")
            solver.compute_iis("infeasible.ilp")
            raise ValueError(f"Schedule is infeasible for {day_of_week}. Check locked shifts and availability.")

        if result.status == SolverStatus.ERROR:
            raise ValueError(f"Solver failed for {day_of_week}")

        day_dummy_cost = 0
        unfilled = []
        for t_idx, t in enumerate(timePeriods):
            dummy_val = result.dummy_values.get(t, 0)
            if dummy_val > 0.5:
                workers_needed = int(round(dummy_val))
                day_dummy_cost += workers_needed * DUMMY_WORKER_COST
                unfilled.append(UnfilledPeriod(
                    period_index=t_idx,
                    start_time=period_to_time(store_start_time, t_idx),
                    end_time=period_to_time(store_start_time, t_idx + 1),
                    workers_needed=workers_needed,
                ))

        day_short_shift_penalty = 0
        for b in employees:
            penalty_val = result.short_shift_hours.get(b, 0)
            if penalty_val > 0.01:
                day_short_shift_penalty += penalty_val * SHORT_SHIFT_PENALTY

        total_dummy_cost += day_dummy_cost
        total_short_shift_cost += day_short_shift_penalty

        df_wide = extract_schedule_dataframe_from_result(result, employees, timePeriods)

        logging.info(f"Schedule for {day_of_week} (using {solver_type}):")
        logging.info(f"\tLabor Cost: ${result.objective_value - day_dummy_cost - day_short_shift_penalty:.2f}")
        if day_dummy_cost > 0:
            logging.warning(f"\tUnfilled shifts penalty: ${day_dummy_cost:.2f} ({len(unfilled)} periods)")
        if day_short_shift_penalty > 0:
            logging.warning(f"\tShort shift penalty: ${day_short_shift_penalty:.2f}")
        logging.info(f"\n{df_wide}")

        day_schedules, day_summary = convert_schedule_to_structured(
            df_wide, day_of_week, store_start_time, result.objective_value,
            unfilled_periods=unfilled,
            dummy_worker_cost=day_dummy_cost,
            min_shift_hours=data_import.config.min_shift_hours,
            actual_date=actual_date_str,
            break_periods=result.break_periods,
        )
        all_schedules.extend(day_schedules)
        daily_summaries.append(day_summary)
        total_weekly_cost += result.objective_value

        # Track end times for rest-between-shifts compliance (for next day)
        previous_day_end_times = {}
        for schedule in day_schedules:
            if schedule.shift_end and schedule.total_hours > 0:
                previous_day_end_times[schedule.employee_name] = schedule.shift_end
                logging.debug(f"Tracking end time for {schedule.employee_name}: {schedule.shift_end}")

        # Move to next date
        current_date += timedelta(days=1)

    has_warnings = total_dummy_cost > 0 or total_short_shift_cost > 0

    return WeeklyScheduleResult(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        store_name=store_name,
        generated_at=datetime.now().isoformat(),
        schedules=all_schedules,
        daily_summaries=daily_summaries,
        total_weekly_cost=total_weekly_cost,
        status="optimal",
        total_dummy_worker_cost=total_dummy_cost,
        total_short_shift_penalty=total_short_shift_cost,
        has_warnings=has_warnings,
    )


if '__name__' == '__main__':
    main()