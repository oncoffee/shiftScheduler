from data_manipulation import putting_store_time_in_df, creating_employee_df
from dateutil import parser
import data_import
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta, date as date_type

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


DAY_OF_WEEK_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


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
) -> tuple[list[EmployeeDaySchedule], DayScheduleSummary]:
    """Convert pivot table to structured schedule data"""
    employee_schedules = []

    for employee in df_wide.index:
        periods = []
        scheduled_periods = []

        for period_idx, col in enumerate(df_wide.columns):
            start_time = period_to_time(store_start_time, period_idx)
            end_time = period_to_time(store_start_time, period_idx + 1)
            scheduled = df_wide.loc[employee, col] == "*"

            period = ShiftPeriod(
                period_index=period_idx,
                start_time=start_time,
                end_time=end_time,
                scheduled=scheduled,
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


def setup_logging():
    open('myapp.log', 'w').close()
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%m-%d %H:%M',
        filename='myapp.log',
        filemode='w'
    )
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s'))
    logging.getLogger('').addHandler(console)


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
            return [2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 3, 3, 3, 3, 3, 3, 2, 2]
        return [2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 3, 3, 3, 3, 3, 3, 2, 2]

    day_type = "weekend" if day_of_week in ('Saturday', 'Sunday') else "weekday"
    relevant_reqs = [r for r in staffing_requirements if r.get("day_type") == day_type]

    store_start_mins = store_start_time.hour * 60 + store_start_time.minute
    store_end_mins = store_end_time.hour * 60 + store_end_time.minute
    if store_end_mins <= store_start_mins:
        store_end_mins = 24 * 60

    num_periods = (store_end_mins - store_start_mins) // 30
    minimum_workers = []

    for period_idx in range(num_periods):
        period_start = store_start_mins + (period_idx * 30)
        period_end = period_start + 30

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
) -> WeeklyScheduleResult:
    data_import.load_data()
    setup_logging()

    hourly_rates = data_import.rates
    maximum_periods = int(data_import.config.max_daily_hours * 2)

    employee_min_hrs = data_import.min_hrs_pr_wk

    all_schedules: list[EmployeeDaySchedule] = []
    daily_summaries: list[DayScheduleSummary] = []
    total_weekly_cost = 0.0
    total_dummy_cost = 0.0
    total_short_shift_cost = 0.0
    store_name = ""

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

        solver_config = SolverConfig(
            dummy_worker_cost=DUMMY_WORKER_COST,
            short_shift_penalty=SHORT_SHIFT_PENALTY,
            min_shift_hours=data_import.config.min_shift_hours,
            max_daily_hours=data_import.config.max_daily_hours,
        )

        problem = ScheduleProblem(
            employees=employees,
            time_periods=timePeriods,
            employee_availability=employee_availability,
            hourly_rates=hourly_rates,
            minimum_workers=minimum_workers,
            locked_periods=locked_periods_set,
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
        )
        all_schedules.extend(day_schedules)
        daily_summaries.append(day_summary)
        total_weekly_cost += result.objective_value

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