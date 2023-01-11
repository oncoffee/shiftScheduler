import gurobipy as gp
from gurobipy import GRB

B = 2
T = 14
timeperiods = range(T)

employee_availability = {
    "Tom": [1 for i in timeperiods],
    "Alex": [1 for i in timeperiods],
    "Bri": [1, 1, 0,
            1, 1, 1,
            1, 1, 1, 0,
            1, 1, 1 ,1]
}


employees = ["Tom", "Bri", "Alex"]
hourly_rates = {"Tom": 10,
                "Bri": 15,
                "Alex": 16}

minimum_workers = [1, 1, 1,
                   2, 2, 2,
                   1, 1, 1, 2,
                   1, 1, 1, 1]
maximum_hours = 11

# Create a new model
m = gp.Model("shop_schedule")

# Create variables
s = m.addVars(employees, timeperiods, vtype=GRB.BINARY, name="s")
w = m.addVars(employees, timeperiods, lb=-1, ub=1, name="w")
v = m.addVars(employees, timeperiods, name="v")
avail = m.addVars(employees, timeperiods, vtype=GRB.BINARY, name="avail")

# Set Objective
m.setObjective(
    gp.quicksum([(hourly_rates[b]*s[b,t]) for b in employees for t in timeperiods]),sense=GRB.MINIMIZE
)

# Ensure availability matches the data
for b in employees:
    for t in timeperiods:
        m.addConstr(avail[b, t] == employee_availability[b][t], f"availability for {b}-{t}")

# Constrain schedule based on availability
for b in employees:
    for t in timeperiods:
        m.addConstr(s[b, t] <= avail[b, t], f"availability constraint for {b}-{t}")


# Add constraint on maximum daily hours
for b in employees:
    m.addConstr(gp.quicksum([s[b,t] for t in timeperiods]) <= maximum_hours, name="max_daily_hours")

# Add constraint on minimum hourly workers
for t in range(1,T):
    m.addConstr(gp.quicksum([s[b,t] for b in employees]) >= minimum_workers[t], name="min_workers")

# Add constraint to count shifts
m.addConstrs((w[b,t] == (s[(b,t)] - s[(b,t-1)])
              for b in employees for t in range(1,T)),
             name="shift changes")

m.addConstrs((w[(b,0)] == s[(b,0)] for b in employees),
             name="shift_starts_init")

m.addConstrs((v[(b,t)] == gp.max_(w[(b,t)],0)
              for b in employees for t in range(1,T)),
             name="shift starts")

# Add constraints to place maximum on shift starts
m.addConstrs((gp.quicksum([v[b,t] for t in timeperiods]) <= 1 for b in employees),
             name="shift_start_max")

# Solving the solver
m.optimize()
m.write('scheduler.lp')
#m.computeIIS()
#for c in m.getConstrs():
#    if c.IISConstr:
#        print("Constraint", c.ConstrName, "is in the IIS")

for v in m.getVars():
    print('%s %g' % (v.VarName, v.X))