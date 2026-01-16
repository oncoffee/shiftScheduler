from data_manipulation import putting_store_time_in_df, creating_employee_df
from dateutil import parser
import data_import
import gurobipy as gp
import pandas as pd
from gurobipy import GRB
import numpy as np
import logging
from datetime import datetime, timedelta

from schemas import (
    ShiftPeriod,
    EmployeeDaySchedule,
    DayScheduleSummary,
    WeeklyScheduleResult,
    UnfilledPeriod,
)


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


def extract_schedule_dataframe(model) -> pd.DataFrame:
    var_data = [(v.VarName, v.X) for v in model.getVars() if v.VarName.startswith("s[")]
    df = pd.DataFrame(var_data, columns=["varname", "status"])
    df["name-period"] = df.varname.str[2:-1]
    df["name-period"] = df["name-period"].str.strip("[]").str.replace('"', "").str.replace(" ", "").str.split(",")
    df["employee"] = df["name-period"].apply(lambda x: x[0])
    df["period"] = df["name-period"].apply(lambda x: x[1])
    df = df[["employee", "period", "status"]].copy()
    df["status"] = np.where(df["status"] == 1, "*", "-")
    cols = df["period"].unique()
    df_wide = pd.pivot(df, index="employee", columns="period", values="status")
    return df_wide[cols]


def main(locked_shifts: list[dict] | None = None, staffing_requirements: list[dict] | None = None) -> WeeklyScheduleResult:
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
    week_no = 0
    store_name = ""

    for s in data_import.stores:
        week_no = s.week_no
        store_name = s.store_name
        day_of_week = s.day_of_week

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
        MIN_SHIFT_PERIODS = int(data_import.config.min_shift_hours * 2)

        m = gp.Model("shop_schedule_1")
        m.setParam("LogToConsole", 0)

        scheduled = m.addVars(employees, timePeriods, vtype=GRB.BINARY, name="s")
        shift_change = m.addVars(employees, timePeriods, lb=-1, ub=1, name="w")
        shift_start = m.addVars(employees, timePeriods, name="v")
        avail = m.addVars(employees, timePeriods, vtype=GRB.BINARY, name="avail")
        works = m.addVars(employees, vtype=GRB.BINARY, name="works")
        dummy = m.addVars(timePeriods, vtype=GRB.INTEGER, lb=0, name="dummy")
        short_shift_hours = m.addVars(employees, lb=0, name="short_shift")

        m.setObjective(
            gp.quicksum([(hourly_rates[b] * scheduled[b, t]) for b in employees for t in timePeriods])
            + gp.quicksum([DUMMY_WORKER_COST * dummy[t] for t in timePeriods])
            + gp.quicksum([SHORT_SHIFT_PENALTY * short_shift_hours[b] for b in employees]),
            sense=GRB.MINIMIZE,
        )

        for b in employees:
            m.addConstr(
                gp.quicksum([scheduled[b, t] for t in timePeriods]) <= maximum_periods,
                name=f"max_daily_hours_for_{b}",
            )

        for t in range(1, T):
            m.addConstr(
                gp.quicksum([scheduled[b, t] for b in employees]) + dummy[t] >= minimum_workers[t],
                name=f"min_workers_period_{t}",
            )

        m.addConstrs(
            (shift_change[b, t] == (scheduled[(b, t)] - scheduled[(b, t - 1)]) for b in employees for t in range(1, T)),
            name="shift_changes",
        )
        m.addConstrs((shift_change[(b, 0)] == scheduled[(b, 0)] for b in employees), name="shift_starts_init")
        m.addConstrs(
            (shift_start[(b, t)] == gp.max_(shift_change[(b, t)], 0) for b in employees for t in range(1, T)),
            name="shift_starts",
        )
        m.addConstrs(
            (gp.quicksum([shift_start[b, t] for t in timePeriods]) <= 1 for b in employees),
            name="shift_start_max",
        )

        for b in employees:
            total_periods = gp.quicksum([scheduled[b, t] for t in timePeriods])
            m.addConstr(total_periods <= T * works[b], name=f"works_upper_{b}")
            m.addConstr(total_periods >= works[b], name=f"works_lower_{b}")
            m.addConstr(
                short_shift_hours[b] >= (MIN_SHIFT_PERIODS * 0.5 * works[b]) - (total_periods * 0.5),
                name=f"short_shift_penalty_{b}"
            )

        locked_periods_set = set()
        if locked_shifts:
            for locked in locked_shifts:
                if locked["day_of_week"] == day_of_week:
                    emp = locked["employee_name"]
                    if emp in employees:
                        for period_idx in locked["periods"]:
                            if period_idx < len(timePeriods):
                                locked_periods_set.add((emp, period_idx))
                        logging.info(f"Locked shift for {emp} on {day_of_week}: periods {locked['periods']}")

        for b in employees:
            for t in timePeriods:
                t_idx = timePeriods.index(t)
                is_locked = (b, t_idx) in locked_periods_set
                if is_locked:
                    m.addConstr(scheduled[b, t] == 1, name=f"locked_{b}_{t}")
                else:
                    m.addConstr(avail[b, t] == employee_availability[b][t_idx], f"availability_for_{b}-{t}")
                    m.addConstr(scheduled[b, t] <= avail[b, t], f"availability_constraint_for_{b}-{t}")

        m.optimize()
        m.write("scheduler.lp")

        if m.status == GRB.INFEASIBLE:
            logging.error(f"Model infeasible for {day_of_week}. Computing IIS...")
            m.computeIIS()
            m.write("infeasible.ilp")
            raise ValueError(f"Schedule is infeasible for {day_of_week}. Check locked shifts and availability.")

        if m.status != GRB.OPTIMAL and m.status != GRB.SUBOPTIMAL:
            raise ValueError(f"Solver failed for {day_of_week} with status {m.status}")

        day_dummy_cost = 0
        unfilled = []
        for t_idx, t in enumerate(timePeriods):
            dummy_val = dummy[t].X
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
            penalty_val = short_shift_hours[b].X
            if penalty_val > 0.01:
                day_short_shift_penalty += penalty_val * SHORT_SHIFT_PENALTY

        total_dummy_cost += day_dummy_cost
        total_short_shift_cost += day_short_shift_penalty

        df_wide = extract_schedule_dataframe(m)

        logging.info(f"Schedule for {day_of_week}:")
        logging.info(f"\tLabor Cost: ${m.objVal - day_dummy_cost - day_short_shift_penalty:.2f}")
        if day_dummy_cost > 0:
            logging.warning(f"\tUnfilled shifts penalty: ${day_dummy_cost:.2f} ({len(unfilled)} periods)")
        if day_short_shift_penalty > 0:
            logging.warning(f"\tShort shift penalty: ${day_short_shift_penalty:.2f}")
        logging.info(f"\n{df_wide}")

        day_schedules, day_summary = convert_schedule_to_structured(
            df_wide, day_of_week, store_start_time, m.objVal,
            unfilled_periods=unfilled,
            dummy_worker_cost=day_dummy_cost,
            min_shift_hours=data_import.config.min_shift_hours,
        )
        all_schedules.extend(day_schedules)
        daily_summaries.append(day_summary)
        total_weekly_cost += m.objVal

    has_warnings = total_dummy_cost > 0 or total_short_shift_cost > 0

    return WeeklyScheduleResult(
        week_no=week_no,
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