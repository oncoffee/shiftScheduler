"""Google OR-Tools CP-SAT implementation of the shift scheduling solver."""

import time
from ortools.sat.python import cp_model

from .types import (
    ScheduleProblem,
    SolverConfig,
    SolverResult,
    SolverStatus,
)


class ORToolsSolver:
    """Shift scheduler using Google OR-Tools CP-SAT solver."""

    def __init__(self):
        self._model: cp_model.CpModel | None = None
        self._solver: cp_model.CpSolver | None = None

    def solve(
        self,
        problem: ScheduleProblem,
        config: SolverConfig,
    ) -> SolverResult:
        """Solve the scheduling problem using OR-Tools CP-SAT."""
        start_time = time.time()

        employees = problem.employees
        time_periods = problem.time_periods
        T = len(time_periods)

        maximum_periods = int(config.max_daily_hours * 2)
        min_shift_periods = int(config.min_shift_hours * 2)

        # Scale costs to integers (CP-SAT requires integer coefficients)
        # Use 100x scaling to preserve 2 decimal places
        SCALE = 100
        scaled_dummy_cost = int(config.dummy_worker_cost * SCALE)
        scaled_short_penalty = int(config.short_shift_penalty * SCALE)

        model = cp_model.CpModel()
        self._model = model

        # Decision variables
        scheduled = {}
        for b in employees:
            for t in time_periods:
                scheduled[(b, t)] = model.NewBoolVar(f"s_{b}_{t}")

        shift_change = {}
        for b in employees:
            for t in time_periods:
                # shift_change in [-1, 1]
                shift_change[(b, t)] = model.NewIntVar(-1, 1, f"w_{b}_{t}")

        shift_start = {}
        for b in employees:
            for t in time_periods:
                # shift_start in [0, 1] (max of shift_change and 0)
                shift_start[(b, t)] = model.NewIntVar(0, 1, f"v_{b}_{t}")

        works = {}
        for b in employees:
            works[b] = model.NewBoolVar(f"works_{b}")

        dummy = {}
        for t in time_periods:
            # Reasonable upper bound for dummy workers
            dummy[t] = model.NewIntVar(0, 20, f"dummy_{t}")

        short_shift_hours = {}
        for b in employees:
            # Short shift hours scaled (max would be min_shift_hours * SCALE / 2)
            max_short = int(config.min_shift_hours * SCALE)
            short_shift_hours[b] = model.NewIntVar(0, max_short, f"short_shift_{b}")

        on_break = {}
        for b in employees:
            for t in time_periods:
                on_break[(b, t)] = model.NewBoolVar(f"break_{b}_{t}")

        needs_break = {}
        for b in employees:
            needs_break[b] = model.NewBoolVar(f"needs_break_{b}")

        # Objective: minimize labor cost + dummy worker penalties + short shift penalties
        # Scale hourly rates to integers
        objective_terms = []

        for b in employees:
            scaled_rate = int(problem.hourly_rates[b] * SCALE)
            for t in time_periods:
                objective_terms.append(scaled_rate * scheduled[(b, t)])

        for t in time_periods:
            objective_terms.append(scaled_dummy_cost * dummy[t])

        for b in employees:
            objective_terms.append(scaled_short_penalty * short_shift_hours[b])

        model.Minimize(sum(objective_terms))

        # Constraint: maximum daily hours per employee
        for b in employees:
            model.Add(
                sum(scheduled[(b, t)] for t in time_periods) <= maximum_periods
            )

        # Constraint: minimum workers per period (skip first period)
        # Workers on break don't count toward minimum staffing
        for t_idx in range(1, T):
            t = time_periods[t_idx]
            model.Add(
                sum(scheduled[(b, t)] - on_break[(b, t)] for b in employees) + dummy[t]
                >= problem.minimum_workers[t_idx]
            )

        # Shift change tracking
        for b in employees:
            for t_idx, t in enumerate(time_periods):
                if t_idx > 0:
                    prev_t = time_periods[t_idx - 1]
                    model.Add(
                        shift_change[(b, t)]
                        == scheduled[(b, t)] - scheduled[(b, prev_t)]
                    )
                else:
                    model.Add(shift_change[(b, t)] == scheduled[(b, t)])

        # Use OR-Tools native AddMaxEquality for shift_start = max(shift_change, 0)
        for b in employees:
            for t_idx, t in enumerate(time_periods):
                if t_idx > 0:
                    # Create a constant 0 variable for max comparison
                    zero = model.NewConstant(0)
                    model.AddMaxEquality(shift_start[(b, t)], [shift_change[(b, t)], zero])
                else:
                    # First period
                    model.Add(shift_start[(b, t)] == scheduled[(b, t)])

        # Maximum one shift start per employee per day
        for b in employees:
            model.Add(sum(shift_start[(b, t)] for t in time_periods) <= 1)

        # Works indicator and short shift penalty
        for b in employees:
            total_periods = sum(scheduled[(b, t)] for t in time_periods)
            model.Add(total_periods <= T * works[b])
            model.Add(total_periods >= works[b])
            # Short shift penalty (scaled by SCALE/2 since we're dealing with half-hours)
            # short_shift_hours >= (min_shift_periods * 0.5 * works) - (total_periods * 0.5)
            # Multiply by SCALE: short_shift_hours * SCALE >= min_shift_periods * SCALE/2 * works - total_periods * SCALE/2
            # We already have short_shift_hours in scaled units
            scaled_min = int(min_shift_periods * SCALE // 2)
            model.Add(
                short_shift_hours[b]
                >= scaled_min * works[b] - int(SCALE // 2) * total_periods
            )

        # Availability and locked period constraints
        for b in employees:
            for t_idx, t in enumerate(time_periods):
                is_locked = (b, t_idx) in problem.locked_periods
                if is_locked:
                    model.Add(scheduled[(b, t)] == 1)
                else:
                    avail_val = problem.employee_availability[b][t_idx]
                    if avail_val == 0:
                        # Not available, cannot schedule
                        model.Add(scheduled[(b, t)] == 0)
                    # If avail_val == 1, no constraint needed (can be 0 or 1)

        if config.meal_break_enabled:
            meal_break_threshold_periods = int(config.meal_break_threshold_hours * 2)

            for b in employees:
                total_periods = sum(scheduled[(b, t)] for t in time_periods)

                exceeds_threshold = model.NewBoolVar(f"exceeds_threshold_{b}")

                model.Add(total_periods >= meal_break_threshold_periods + 1).OnlyEnforceIf(exceeds_threshold)
                model.Add(total_periods <= meal_break_threshold_periods).OnlyEnforceIf(exceeds_threshold.Not())

                model.AddImplication(exceeds_threshold, needs_break[b])

                for t_idx, t in enumerate(time_periods):
                    model.AddImplication(on_break[(b, t)], scheduled[(b, t)])

                model.Add(
                    sum(on_break[(b, t)] for t in time_periods)
                    >= config.meal_break_duration_periods
                ).OnlyEnforceIf(needs_break[b])

                for t_idx, t in enumerate(time_periods):
                    if t_idx > 0 and t_idx < T - 1:
                        t_prev = time_periods[t_idx - 1]
                        t_next = time_periods[t_idx + 1]
                        model.AddImplication(on_break[(b, t)], scheduled[(b, t_prev)])
                        model.AddImplication(on_break[(b, t)], scheduled[(b, t_next)])
                    else:
                        model.Add(on_break[(b, t)] == 0)

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.log_search_progress = False
        self._solver = solver
        status = solver.Solve(model)

        solve_time = time.time() - start_time

        # Handle status
        if status == cp_model.INFEASIBLE:
            return SolverResult(
                status=SolverStatus.INFEASIBLE,
                objective_value=float("inf"),
                schedule_matrix={},
                dummy_values={},
                short_shift_hours={},
                break_periods={},
                solve_time=solve_time,
            )

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return SolverResult(
                status=SolverStatus.ERROR,
                objective_value=float("inf"),
                schedule_matrix={},
                dummy_values={},
                short_shift_hours={},
                break_periods={},
                solve_time=solve_time,
            )

        # Extract solution (descale objective)
        schedule_matrix = {}
        for b in employees:
            for t in time_periods:
                schedule_matrix[(b, t)] = solver.Value(scheduled[(b, t)])

        dummy_vals = {t: float(solver.Value(dummy[t])) for t in time_periods}
        short_shift_vals = {
            b: solver.Value(short_shift_hours[b]) / SCALE for b in employees
        }

        # Extract break periods
        break_periods = {}
        for b in employees:
            emp_breaks = []
            for t_idx, t in enumerate(time_periods):
                if solver.Value(on_break[(b, t)]) == 1:
                    emp_breaks.append(t_idx)
            if emp_breaks:
                break_periods[b] = emp_breaks

        result_status = (
            SolverStatus.OPTIMAL if status == cp_model.OPTIMAL else SolverStatus.SUBOPTIMAL
        )

        return SolverResult(
            status=result_status,
            objective_value=solver.ObjectiveValue() / SCALE,
            schedule_matrix=schedule_matrix,
            dummy_values=dummy_vals,
            short_shift_hours=short_shift_vals,
            break_periods=break_periods,
            solve_time=solve_time,
        )

    def write_model(self, filename: str) -> None:
        """Write the OR-Tools model to file (proto format)."""
        if self._model:
            with open(filename, "w") as f:
                f.write(str(self._model.Proto()))

    def compute_iis(self, filename: str) -> None:
        """Compute IIS - not natively supported in CP-SAT, write model instead."""
        # CP-SAT doesn't have IIS like Gurobi
        # Write the model for debugging
        self.write_model(filename)
