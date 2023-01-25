from data_manipulation import *
import gurobipy as gp
import pandas as pd
from gurobipy import GRB
import numpy as np


def main():
    hourly_rates = rates
    maximum_hours = 22

    employee_min_hrs = min_hrs_pr_wk

    for s in stores:
        week_no = s.week_no
        store_name = s.store_name
        day_of_week = s.day_of_week

        if day_of_week in ('Saturday', 'Sunday'):
            minimum_workers = [2, 2, 2, 2,
                               3, 3, 3, 3, 3, 3, 3, 4,
                               4, 4, 4, 3, 3, 3, 3, 3,
                               3, 2, 2]
        elif day_of_week in ('Monday', 'Tuesday', 'Wednesday',
                             'Thursday', 'Friday'):
            minimum_workers = [2, 2, 2, 2, 2, 3,
                               3, 3, 3, 3, 4, 4, 4, 4,
                               4, 4, 4, 3, 3, 3, 3, 3,
                               3, 2, 2]

        store_start_time = parser.parse(s.start_time).time()
        store_end_time = parser.parse(s.end_time).time()

        store_df = putting_store_time_in_df(s.day_of_week, store_start_time,
                                            store_end_time)

        for sch in schedule:
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
            store_df = store_df.replace(np.NaN, 0)
        #print(store_df)

        employees = [x for x in store_df.columns][3:]
        timePeriods = [x for x in store_df.Period]
        T = len(timePeriods)
        B = len(employees)

        employee_availability = {col: store_df[col].tolist()
                                 for col in store_df[[emp for emp in employees]].columns}

        # Create a new model
        m = gp.Model("shop_schedule_1")

        # Create variables
        s = m.addVars(employees, timePeriods, vtype=GRB.BINARY, name="s")
        w = m.addVars(employees, timePeriods, lb=-1, ub=1, name="w")
        v = m.addVars(employees, timePeriods, name="v")
        avail = m.addVars(employees, timePeriods, vtype=GRB.BINARY, name="avail")

        # Set Objective
        m.setObjective(
            gp.quicksum([(hourly_rates[b] * s[b, t]) for b in employees for t in timePeriods]),
            sense=GRB.MINIMIZE,
        )

        # Ensure availability matches the data
        for b in employees:
            for t in timePeriods:
                m.addConstr(
                    avail[b, t] == employee_availability[b][t], f"availability_for_{b}-{t}"
                )

        # Constrain schedule based on availability
        for b in employees:
            for t in timePeriods:
                m.addConstr(s[b, t] <= avail[b, t], f"availability_constraint_for_{b}-{t}")


        # Add constraint on maximum daily hours
        for b in employees:
            m.addConstr(
                gp.quicksum([s[b, t] for t in timePeriods]) <= maximum_hours,
                name=f"max_daily_hours_for_{b}",
            )

        # Add constraint on minimum hourly workers
        for t in range(1, T):
            m.addConstr(
                gp.quicksum([s[b, t] for b in employees]) >= minimum_workers[t],
                name=f"min_workers_period_{t}",
            )

        # Add constraint to count shifts
        m.addConstrs(
            (w[b, t] == (s[(b, t)] - s[(b, t - 1)]) for b in employees for t in range(1, T)),
            name="shift_changes",
        )

        m.addConstrs((w[(b, 0)] == s[(b, 0)] for b in employees), name="shift_starts_init")

        m.addConstrs(
            (v[(b, t)] == gp.max_(w[(b, t)], 0) for b in employees for t in range(1, T)),
            name="shift_starts",
        )

        # Add constraints to place maximum on shift starts
        m.addConstrs(
            (gp.quicksum([v[b, t] for t in timePeriods]) <= 1 for b in employees),
            name="shift_start_max",
        )


        # Solving the solver
        m.optimize()
        m.write("scheduler.lp")

        #m.computeIIS()
        #for c in m.getConstrs():
        #   if c.IISConstr:
        #       print("Constraint", c.ConstrName, "is in the IIS")

        varname = []
        status = []
        for v in m.getVars():
            varname.append(v.VarName)
            status.append(v.X)
            # print('%s %g' % (v.VarName, v.X))
        data = {"varname": varname, "status": status}
        df = pd.DataFrame(data)
        df["var"] = df.varname.str[:1]
        df = df[df["var"] == "s"]
        df["name-period"] = df.varname.str[1:]
        df["name-period"] = df.apply(
            lambda row: row["name-period"]
            .strip("[]")
            .replace('"', "")
            .replace(" ", "")
            .split(","),
            axis=1,
        )
        df["employee"] = df["name-period"].apply(lambda x: x[0])
        df["period"] = df["name-period"].apply(lambda x: x[1])
        df = df[["employee", "period", "status"]].copy()
        df["status"] = np.where(df["status"] == 1, "*", "-")
        cols = df["period"].unique()
        df_wide = pd.pivot(df, index="employee", columns="period", values="status")
        df_wide = df_wide[cols]
        print(f"\nSchedule for {day_of_week}:")
        print(f"\n\tTotal Cost: ${m.objVal}\n")
        print(df_wide)


if '__name__' == '__main__':
    main()