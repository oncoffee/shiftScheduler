"""Gurobi implementation of the shift scheduling solver."""

import time
import gurobipy as gp
from gurobipy import GRB

from .types import (
    ScheduleProblem,
    SolverConfig,
    SolverResult,
    SolverStatus,
)


class GurobiSolver:
    """Shift scheduler using Gurobi optimization solver."""

    def __init__(self):
        self._model: gp.Model | None = None

    def solve(
        self,
        problem: ScheduleProblem,
        config: SolverConfig,
    ) -> SolverResult:
        """Solve the scheduling problem using Gurobi."""
        start_time = time.time()

        employees = problem.employees
        time_periods = problem.time_periods
        T = len(time_periods)

        maximum_periods = int(config.max_daily_hours * 2)
        min_shift_periods = int(config.min_shift_hours * 2)

        m = gp.Model("shift_schedule")
        m.setParam("LogToConsole", 0)
        self._model = m

        # Decision variables
        scheduled = m.addVars(employees, time_periods, vtype=GRB.BINARY, name="s")
        shift_change = m.addVars(employees, time_periods, lb=-1, ub=1, name="w")
        shift_start = m.addVars(employees, time_periods, name="v")
        avail = m.addVars(employees, time_periods, vtype=GRB.BINARY, name="avail")
        works = m.addVars(employees, vtype=GRB.BINARY, name="works")
        dummy = m.addVars(time_periods, vtype=GRB.INTEGER, lb=0, name="dummy")
        short_shift_hours = m.addVars(employees, lb=0, name="short_shift")

        on_break = m.addVars(employees, time_periods, vtype=GRB.BINARY, name="break")
        needs_break = m.addVars(employees, vtype=GRB.BINARY, name="needs_break")

        # Objective: minimize labor cost + dummy worker penalties + short shift penalties
        m.setObjective(
            gp.quicksum(
                problem.hourly_rates[b] * scheduled[b, t]
                for b in employees
                for t in time_periods
            )
            + gp.quicksum(config.dummy_worker_cost * dummy[t] for t in time_periods)
            + gp.quicksum(
                config.short_shift_penalty * short_shift_hours[b] for b in employees
            ),
            sense=GRB.MINIMIZE,
        )

        # Constraint: maximum daily hours per employee
        for b in employees:
            m.addConstr(
                gp.quicksum(scheduled[b, t] for t in time_periods) <= maximum_periods,
                name=f"max_daily_hours_for_{b}",
            )

        # Constraint: minimum workers per period (skip first period)
        # Workers on break don't count toward minimum staffing
        for t_idx in range(1, T):
            t = time_periods[t_idx]
            m.addConstr(
                gp.quicksum(scheduled[b, t] - on_break[b, t] for b in employees)
                + dummy[t]
                >= problem.minimum_workers[t_idx],
                name=f"min_workers_period_{t_idx}",
            )

        # Shift change tracking
        m.addConstrs(
            (
                shift_change[b, t]
                == (scheduled[b, t] - scheduled[b, time_periods[t_idx - 1]])
                for b in employees
                for t_idx, t in enumerate(time_periods)
                if t_idx > 0
            ),
            name="shift_changes",
        )
        m.addConstrs(
            (shift_change[b, time_periods[0]] == scheduled[b, time_periods[0]] for b in employees),
            name="shift_starts_init",
        )

        # Shift start using Gurobi's native max_()
        m.addConstrs(
            (
                shift_start[b, t] == gp.max_(shift_change[b, t], 0)
                for b in employees
                for t_idx, t in enumerate(time_periods)
                if t_idx > 0
            ),
            name="shift_starts",
        )

        # Maximum one shift start per employee per day
        m.addConstrs(
            (
                gp.quicksum(shift_start[b, t] for t in time_periods) <= 1
                for b in employees
            ),
            name="shift_start_max",
        )

        # Works indicator and short shift penalty
        for b in employees:
            total_periods = gp.quicksum(scheduled[b, t] for t in time_periods)
            m.addConstr(total_periods <= T * works[b], name=f"works_upper_{b}")
            m.addConstr(total_periods >= works[b], name=f"works_lower_{b}")
            m.addConstr(
                short_shift_hours[b]
                >= (min_shift_periods * 0.5 * works[b]) - (total_periods * 0.5),
                name=f"short_shift_penalty_{b}",
            )

        # Availability and locked period constraints
        for b in employees:
            for t_idx, t in enumerate(time_periods):
                is_locked = (b, t_idx) in problem.locked_periods
                if is_locked:
                    m.addConstr(scheduled[b, t] == 1, name=f"locked_{b}_{t}")
                else:
                    m.addConstr(
                        avail[b, t] == problem.employee_availability[b][t_idx],
                        name=f"availability_for_{b}-{t}",
                    )
                    m.addConstr(
                        scheduled[b, t] <= avail[b, t],
                        name=f"availability_constraint_for_{b}-{t}",
                    )

        if config.meal_break_enabled:
            meal_break_threshold_periods = int(config.meal_break_threshold_hours * 2)

            for b in employees:
                total_periods = gp.quicksum(scheduled[b, t] for t in time_periods)

                m.addConstr(
                    total_periods - meal_break_threshold_periods <= T * needs_break[b],
                    name=f"needs_break_upper_{b}",
                )
                m.addConstr(
                    total_periods - meal_break_threshold_periods >= 1 - T * (1 - needs_break[b]),
                    name=f"needs_break_lower_{b}",
                )

                for t_idx, t in enumerate(time_periods):
                    m.addConstr(
                        on_break[b, t] <= scheduled[b, t],
                        name=f"break_requires_scheduled_{b}_{t}",
                    )

                m.addConstr(
                    gp.quicksum(on_break[b, t] for t in time_periods)
                    >= config.meal_break_duration_periods * needs_break[b],
                    name=f"min_break_periods_{b}",
                )

                for t_idx, t in enumerate(time_periods):
                    if t_idx > 0 and t_idx < T - 1:
                        t_prev = time_periods[t_idx - 1]
                        t_next = time_periods[t_idx + 1]
                        m.addConstr(
                            on_break[b, t] <= scheduled[b, t_prev],
                            name=f"break_not_first_{b}_{t}",
                        )
                        m.addConstr(
                            on_break[b, t] <= scheduled[b, t_next],
                            name=f"break_not_last_{b}_{t}",
                        )
                    else:
                        m.addConstr(on_break[b, t] == 0, name=f"no_break_boundary_{b}_{t}")

        # Solve
        m.optimize()

        solve_time = time.time() - start_time

        # Handle status
        if m.status == GRB.INFEASIBLE:
            return SolverResult(
                status=SolverStatus.INFEASIBLE,
                objective_value=float("inf"),
                schedule_matrix={},
                dummy_values={},
                short_shift_hours={},
                break_periods={},
                solve_time=solve_time,
            )

        if m.status not in (GRB.OPTIMAL, GRB.SUBOPTIMAL):
            return SolverResult(
                status=SolverStatus.ERROR,
                objective_value=float("inf"),
                schedule_matrix={},
                dummy_values={},
                short_shift_hours={},
                break_periods={},
                solve_time=solve_time,
            )

        # Extract solution
        schedule_matrix = {}
        for b in employees:
            for t in time_periods:
                schedule_matrix[(b, t)] = int(round(scheduled[b, t].X))

        dummy_vals = {t: dummy[t].X for t in time_periods}
        short_shift_vals = {b: short_shift_hours[b].X for b in employees}

        # Extract break periods
        break_periods = {}
        for b in employees:
            emp_breaks = []
            for t_idx, t in enumerate(time_periods):
                if int(round(on_break[b, t].X)) == 1:
                    emp_breaks.append(t_idx)
            if emp_breaks:
                break_periods[b] = emp_breaks

        status = SolverStatus.OPTIMAL if m.status == GRB.OPTIMAL else SolverStatus.SUBOPTIMAL

        return SolverResult(
            status=status,
            objective_value=m.objVal,
            schedule_matrix=schedule_matrix,
            dummy_values=dummy_vals,
            short_shift_hours=short_shift_vals,
            break_periods=break_periods,
            solve_time=solve_time,
        )

    def write_model(self, filename: str) -> None:
        """Write the Gurobi model to file."""
        if self._model:
            self._model.write(filename)

    def compute_iis(self, filename: str) -> None:
        """Compute and write IIS for infeasible model."""
        if self._model:
            self._model.computeIIS()
            self._model.write(filename)
