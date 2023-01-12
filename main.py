import gurobipy as gp
import pandas as pd
from gurobipy import GRB
import numpy as np

B = 2
T = 14
timePeriods = range(T)

employee_availability = {
    "Tom": [1 for i in timePeriods],
    "Alex": [1 for i in timePeriods],
    "Bri": [1, 1, 0, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1],
}


employees = ["Tom", "Bri", "Alex"]
hourly_rates = {"Tom": 10, "Bri": 15, "Alex": 16}

minimum_workers = [1, 1, 1, 2, 2, 2, 1, 1, 1, 2, 1, 1, 1, 1]
maximum_hours = 11

# Create a new model
m = gp.Model("shop_schedule")

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
            avail[b, t] == employee_availability[b][t], f"availability for {b}-{t}"
        )

# Constrain schedule based on availability
for b in employees:
    for t in timePeriods:
        m.addConstr(s[b, t] <= avail[b, t], f"availability constraint for {b}-{t}")


# Add constraint on maximum daily hours
for b in employees:
    m.addConstr(
        gp.quicksum([s[b, t] for t in timePeriods]) <= maximum_hours,
        name="max_daily_hours",
    )

# Add constraint on minimum hourly workers
for t in range(1, T):
    m.addConstr(
        gp.quicksum([s[b, t] for b in employees]) >= minimum_workers[t],
        name="min_workers",
    )

# Add constraint to count shifts
m.addConstrs(
    (w[b, t] == (s[(b, t)] - s[(b, t - 1)]) for b in employees for t in range(1, T)),
    name="shift changes",
)

m.addConstrs((w[(b, 0)] == s[(b, 0)] for b in employees), name="shift_starts_init")

m.addConstrs(
    (v[(b, t)] == gp.max_(w[(b, t)], 0) for b in employees for t in range(1, T)),
    name="shift starts",
)

# Add constraints to place maximum on shift starts
m.addConstrs(
    (gp.quicksum([v[b, t] for t in timePeriods]) <= 1 for b in employees),
    name="shift_start_max",
)

# Solving the solver
m.optimize()
m.write("scheduler.lp")
# m.computeIIS()
# for c in m.getConstrs():
#    if c.IISConstr:
#        print("Constraint", c.ConstrName, "is in the IIS")

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
print("\nSchedule for Monday:")
print(f"\n\tTotal Cost: ${m.objVal}\n")
print(df_wide)
