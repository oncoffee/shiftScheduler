"""PuLP/CBC implementation of the shift scheduling solver."""

import time
import pulp

from .types import (
    ScheduleProblem,
    SolverConfig,
    SolverResult,
    SolverStatus,
)


class PuLPSolver:
    """Shift scheduler using PuLP with CBC solver."""

    def __init__(self):
        self._model: pulp.LpProblem | None = None
        self._model_written = False

    def solve(
        self,
        problem: ScheduleProblem,
        config: SolverConfig,
    ) -> SolverResult:
        """Solve the scheduling problem using PuLP/CBC."""
        start_time = time.time()

        employees = problem.employees
        time_periods = problem.time_periods
        T = len(time_periods)

        maximum_periods = int(config.max_daily_hours * 2)
        min_shift_periods = int(config.min_shift_hours * 2)

        # Big-M constant for linearization (shift_change bounded by [-1, 1])
        M = 1000

        m = pulp.LpProblem("shift_schedule", pulp.LpMinimize)
        self._model = m

        # Decision variables
        scheduled = pulp.LpVariable.dicts(
            "s", ((b, t) for b in employees for t in time_periods), cat=pulp.LpBinary
        )
        shift_change = pulp.LpVariable.dicts(
            "w", ((b, t) for b in employees for t in time_periods), lowBound=-1, upBound=1
        )
        shift_start = pulp.LpVariable.dicts(
            "v", ((b, t) for b in employees for t in time_periods), lowBound=0
        )
        # Binary indicator for max linearization: z=1 if shift_change > 0
        z = pulp.LpVariable.dicts(
            "z", ((b, t) for b in employees for t in time_periods), cat=pulp.LpBinary
        )
        avail = pulp.LpVariable.dicts(
            "avail", ((b, t) for b in employees for t in time_periods), cat=pulp.LpBinary
        )
        works = pulp.LpVariable.dicts("works", employees, cat=pulp.LpBinary)
        dummy = pulp.LpVariable.dicts(
            "dummy", time_periods, lowBound=0, cat=pulp.LpInteger
        )
        short_shift_hours = pulp.LpVariable.dicts(
            "short_shift", employees, lowBound=0
        )

        on_break = pulp.LpVariable.dicts(
            "break", ((b, t) for b in employees for t in time_periods), cat=pulp.LpBinary
        )
        needs_break = pulp.LpVariable.dicts("needs_break", employees, cat=pulp.LpBinary)

        # Objective: minimize labor cost + dummy worker penalties + short shift penalties
        m += (
            pulp.lpSum(
                problem.hourly_rates[b] * scheduled[(b, t)]
                for b in employees
                for t in time_periods
            )
            + pulp.lpSum(config.dummy_worker_cost * dummy[t] for t in time_periods)
            + pulp.lpSum(
                config.short_shift_penalty * short_shift_hours[b] for b in employees
            )
        )

        # Constraint: maximum daily hours per employee
        for b in employees:
            m += (
                pulp.lpSum(scheduled[(b, t)] for t in time_periods) <= maximum_periods,
                f"max_daily_hours_for_{b}",
            )

        # Constraint: minimum workers per period (skip first period)
        # Workers on break don't count toward minimum staffing
        for t_idx in range(1, T):
            t = time_periods[t_idx]
            m += (
                pulp.lpSum(scheduled[(b, t)] - on_break[(b, t)] for b in employees)
                + dummy[t]
                >= problem.minimum_workers[t_idx],
                f"min_workers_period_{t_idx}",
            )

        # Shift change tracking
        for b in employees:
            for t_idx, t in enumerate(time_periods):
                if t_idx > 0:
                    prev_t = time_periods[t_idx - 1]
                    m += (
                        shift_change[(b, t)]
                        == scheduled[(b, t)] - scheduled[(b, prev_t)],
                        f"shift_change_{b}_{t}",
                    )
                else:
                    m += (
                        shift_change[(b, t)] == scheduled[(b, t)],
                        f"shift_starts_init_{b}",
                    )

        # Big-M linearization for shift_start = max(shift_change, 0)
        # shift_start >= shift_change
        # shift_start >= 0 (already enforced by lowBound)
        # shift_start <= shift_change + M*(1-z)  (when z=1, shift_start <= shift_change)
        # shift_start <= M*z                      (when z=0, shift_start <= 0)
        # z=1 when shift_change > 0, z=0 otherwise
        for b in employees:
            for t_idx, t in enumerate(time_periods):
                if t_idx > 0:
                    # shift_start >= shift_change
                    m += (
                        shift_start[(b, t)] >= shift_change[(b, t)],
                        f"shift_start_lb_{b}_{t}",
                    )
                    # shift_start <= shift_change + M*(1-z)
                    m += (
                        shift_start[(b, t)] <= shift_change[(b, t)] + M * (1 - z[(b, t)]),
                        f"shift_start_ub1_{b}_{t}",
                    )
                    # shift_start <= M*z
                    m += (
                        shift_start[(b, t)] <= M * z[(b, t)],
                        f"shift_start_ub2_{b}_{t}",
                    )
                else:
                    # First period: shift_start = max(scheduled, 0) = scheduled (since binary)
                    m += (
                        shift_start[(b, t)] == scheduled[(b, t)],
                        f"shift_start_init_{b}",
                    )

        # Maximum one shift start per employee per day
        for b in employees:
            m += (
                pulp.lpSum(shift_start[(b, t)] for t in time_periods) <= 1,
                f"shift_start_max_{b}",
            )

        # Works indicator and short shift penalty
        for b in employees:
            total_periods = pulp.lpSum(scheduled[(b, t)] for t in time_periods)
            m += (total_periods <= T * works[b], f"works_upper_{b}")
            m += (total_periods >= works[b], f"works_lower_{b}")
            m += (
                short_shift_hours[b]
                >= (min_shift_periods * 0.5 * works[b]) - (total_periods * 0.5),
                f"short_shift_penalty_{b}",
            )

        # Availability and locked period constraints
        for b in employees:
            for t_idx, t in enumerate(time_periods):
                is_locked = (b, t_idx) in problem.locked_periods
                if is_locked:
                    m += (scheduled[(b, t)] == 1, f"locked_{b}_{t}")
                else:
                    m += (
                        avail[(b, t)] == problem.employee_availability[b][t_idx],
                        f"availability_for_{b}_{t}",
                    )
                    m += (
                        scheduled[(b, t)] <= avail[(b, t)],
                        f"availability_constraint_for_{b}_{t}",
                    )

        if config.meal_break_enabled:
            meal_break_threshold_periods = int(config.meal_break_threshold_hours * 2)

            for b in employees:
                total_periods = pulp.lpSum(scheduled[(b, t)] for t in time_periods)

                m += (
                    total_periods - meal_break_threshold_periods <= T * needs_break[b],
                    f"needs_break_upper_{b}",
                )
                m += (
                    total_periods - meal_break_threshold_periods >= 1 - T * (1 - needs_break[b]),
                    f"needs_break_lower_{b}",
                )

                for t_idx, t in enumerate(time_periods):
                    m += (
                        on_break[(b, t)] <= scheduled[(b, t)],
                        f"break_requires_scheduled_{b}_{t}",
                    )

                m += (
                    pulp.lpSum(on_break[(b, t)] for t in time_periods)
                    >= config.meal_break_duration_periods * needs_break[b],
                    f"min_break_periods_{b}",
                )

                for t_idx, t in enumerate(time_periods):
                    if t_idx > 0 and t_idx < T - 1:
                        t_prev = time_periods[t_idx - 1]
                        t_next = time_periods[t_idx + 1]
                        m += (
                            on_break[(b, t)] <= scheduled[(b, t_prev)],
                            f"break_not_first_{b}_{t}",
                        )
                        m += (
                            on_break[(b, t)] <= scheduled[(b, t_next)],
                            f"break_not_last_{b}_{t}",
                        )
                    else:
                        m += (on_break[(b, t)] == 0, f"no_break_boundary_{b}_{t}")

        # Solve
        solver = pulp.PULP_CBC_CMD(msg=0)
        status = m.solve(solver)

        solve_time = time.time() - start_time

        # Handle status
        if status == pulp.LpStatusInfeasible:
            return SolverResult(
                status=SolverStatus.INFEASIBLE,
                objective_value=float("inf"),
                schedule_matrix={},
                dummy_values={},
                short_shift_hours={},
                break_periods={},
                solve_time=solve_time,
            )

        if status not in (pulp.LpStatusOptimal,):
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
                val = scheduled[(b, t)].varValue
                schedule_matrix[(b, t)] = int(round(val)) if val is not None else 0

        dummy_vals = {t: dummy[t].varValue or 0 for t in time_periods}
        short_shift_vals = {b: short_shift_hours[b].varValue or 0 for b in employees}

        # Extract break periods
        break_periods = {}
        for b in employees:
            emp_breaks = []
            for t_idx, t in enumerate(time_periods):
                val = on_break[(b, t)].varValue
                if val is not None and int(round(val)) == 1:
                    emp_breaks.append(t_idx)
            if emp_breaks:
                break_periods[b] = emp_breaks

        return SolverResult(
            status=SolverStatus.OPTIMAL,
            objective_value=pulp.value(m.objective),
            schedule_matrix=schedule_matrix,
            dummy_values=dummy_vals,
            short_shift_hours=short_shift_vals,
            break_periods=break_periods,
            solve_time=solve_time,
        )

    def write_model(self, filename: str) -> None:
        """Write the PuLP model to file."""
        if self._model:
            self._model.writeLP(filename)

    def compute_iis(self, filename: str) -> None:
        """Compute IIS - not supported in PuLP/CBC, write a placeholder."""
        # CBC doesn't have native IIS support like Gurobi
        # Write the model instead for debugging
        if self._model:
            self._model.writeLP(filename.replace(".ilp", ".lp"))
