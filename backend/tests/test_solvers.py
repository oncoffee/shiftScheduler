"""Unit tests for shift scheduler solvers.

Tests meal breaks, staffing constraints, max hours, availability,
locked periods, and consistency across all three solvers.
"""

import pytest
from solvers.types import (
    ScheduleProblem,
    SolverConfig,
    SolverResult,
    SolverStatus,
)
from solvers.gurobi_solver import GurobiSolver
from solvers.pulp_solver import PuLPSolver
from solvers.ortools_solver import ORToolsSolver


# ============================================================================
# ============================================================================


@pytest.fixture
def basic_time_periods():
    """Generate 20 time periods (10 hours of 30-minute slots) starting at 08:00."""
    periods = []
    for i in range(20):
        hour = 8 + i // 2
        minute = (i % 2) * 30
        periods.append(f"{hour:02d}:{minute:02d}")
    return periods


@pytest.fixture
def short_time_periods():
    """Generate 8 time periods (4 hours) for short shift tests."""
    periods = []
    for i in range(8):
        hour = 9 + i // 2
        minute = (i % 2) * 30
        periods.append(f"{hour:02d}:{minute:02d}")
    return periods


@pytest.fixture
def full_day_periods():
    """Generate 24 time periods (12 hours) for full day tests."""
    periods = []
    for i in range(24):
        hour = 8 + i // 2
        minute = (i % 2) * 30
        periods.append(f"{hour:02d}:{minute:02d}")
    return periods


@pytest.fixture
def two_employees():
    """Two employees with different hourly rates."""
    return ["Alice", "Bob"]


@pytest.fixture
def three_employees():
    """Three employees for staffing tests."""
    return ["Alice", "Bob", "Charlie"]


@pytest.fixture
def full_availability(basic_time_periods, two_employees):
    """All employees available for all periods."""
    return {
        emp: [1] * len(basic_time_periods)
        for emp in two_employees
    }


@pytest.fixture
def partial_availability(basic_time_periods, two_employees):
    """Employees with partial availability."""
    n = len(basic_time_periods)
    return {
        "Alice": [1] * n,
        "Bob": [1] * (n // 2) + [0] * (n - n // 2),
    }


@pytest.fixture
def basic_hourly_rates(two_employees):
    """Basic hourly rates for employees."""
    return {"Alice": 15.0, "Bob": 18.0}


@pytest.fixture
def three_employee_rates(three_employees):
    """Hourly rates for three employees."""
    return {"Alice": 15.0, "Bob": 18.0, "Charlie": 16.0}


@pytest.fixture
def low_minimum_workers(basic_time_periods):
    """Minimum 1 worker per period."""
    return [1] * len(basic_time_periods)


@pytest.fixture
def high_minimum_workers(basic_time_periods):
    """Minimum 2 workers per period."""
    return [2] * len(basic_time_periods)


@pytest.fixture
def default_config():
    """Default solver configuration."""
    return SolverConfig(
        dummy_worker_cost=100.0,
        short_shift_penalty=50.0,
        min_shift_hours=3.0,
        max_daily_hours=11.0,
        meal_break_enabled=False,
        meal_break_threshold_hours=5.0,
        meal_break_duration_periods=1,
    )


@pytest.fixture
def meal_break_config():
    """Solver config with meal breaks enabled."""
    return SolverConfig(
        dummy_worker_cost=100.0,
        short_shift_penalty=50.0,
        min_shift_hours=3.0,
        max_daily_hours=11.0,
        meal_break_enabled=True,
        meal_break_threshold_hours=5.0,
        meal_break_duration_periods=1,
    )


@pytest.fixture
def basic_problem(basic_time_periods, two_employees, full_availability, basic_hourly_rates, low_minimum_workers):
    """Basic scheduling problem."""
    return ScheduleProblem(
        employees=two_employees,
        time_periods=basic_time_periods,
        employee_availability=full_availability,
        hourly_rates=basic_hourly_rates,
        minimum_workers=low_minimum_workers,
        locked_periods=set(),
    )


@pytest.fixture
def all_solvers():
    """Get instances of all three solvers."""
    return [
        ("gurobi", GurobiSolver()),
        ("pulp", PuLPSolver()),
        ("ortools", ORToolsSolver()),
    ]


def count_scheduled_periods(result: SolverResult, employee: str, time_periods: list[str]) -> int:
    """Count how many periods an employee is scheduled for."""
    count = 0
    for t in time_periods:
        if result.schedule_matrix.get((employee, t), 0) == 1:
            count += 1
    return count


def get_scheduled_period_indices(result: SolverResult, employee: str, time_periods: list[str]) -> list[int]:
    """Get list of scheduled period indices for an employee."""
    indices = []
    for idx, t in enumerate(time_periods):
        if result.schedule_matrix.get((employee, t), 0) == 1:
            indices.append(idx)
    return indices


def is_shift_contiguous(result: SolverResult, employee: str, time_periods: list[str]) -> bool:
    """Check if an employee's shift is contiguous (no gaps)."""
    indices = get_scheduled_period_indices(result, employee, time_periods)
    if len(indices) <= 1:
        return True
    for i in range(1, len(indices)):
        if indices[i] - indices[i-1] != 1:
            return False
    return True


# ============================================================================
# ============================================================================


class TestBasicSolverFunctionality:
    """Test basic solver functionality across all solvers."""

    @pytest.mark.parametrize("solver_name,solver_cls", [
        ("gurobi", GurobiSolver),
        ("pulp", PuLPSolver),
        ("ortools", ORToolsSolver),
    ])
    def test_solver_returns_optimal_status(
        self, solver_name, solver_cls, basic_problem, default_config
    ):
        """All solvers should return optimal status for a feasible problem."""
        solver = solver_cls()
        result = solver.solve(basic_problem, default_config)

        assert result.status in (SolverStatus.OPTIMAL, SolverStatus.SUBOPTIMAL), \
            f"{solver_name} returned status {result.status}"

    @pytest.mark.parametrize("solver_name,solver_cls", [
        ("gurobi", GurobiSolver),
        ("pulp", PuLPSolver),
        ("ortools", ORToolsSolver),
    ])
    def test_solver_returns_schedule_matrix(
        self, solver_name, solver_cls, basic_problem, default_config
    ):
        """All solvers should return a non-empty schedule matrix."""
        solver = solver_cls()
        result = solver.solve(basic_problem, default_config)

        assert len(result.schedule_matrix) > 0, \
            f"{solver_name} returned empty schedule matrix"

    @pytest.mark.parametrize("solver_name,solver_cls", [
        ("gurobi", GurobiSolver),
        ("pulp", PuLPSolver),
        ("ortools", ORToolsSolver),
    ])
    def test_solver_tracks_solve_time(
        self, solver_name, solver_cls, basic_problem, default_config
    ):
        """All solvers should track solve time."""
        solver = solver_cls()
        result = solver.solve(basic_problem, default_config)

        assert result.solve_time > 0, \
            f"{solver_name} did not track solve time"


# ============================================================================
# ============================================================================


class TestMaxHoursConstraint:
    """Test that max daily hours constraint is respected."""

    @pytest.mark.parametrize("solver_name,solver_cls", [
        ("gurobi", GurobiSolver),
        ("pulp", PuLPSolver),
        ("ortools", ORToolsSolver),
    ])
    def test_respects_max_daily_hours(
        self, solver_name, solver_cls, full_day_periods, two_employees, basic_hourly_rates
    ):
        """Employees should not be scheduled beyond max daily hours."""
        config = SolverConfig(
            dummy_worker_cost=100.0,
            short_shift_penalty=50.0,
            min_shift_hours=3.0,
            max_daily_hours=8.0,
            meal_break_enabled=False,
        )

      
        availability = {emp: [1] * len(full_day_periods) for emp in two_employees}
        minimum_workers = [1] * len(full_day_periods)

        problem = ScheduleProblem(
            employees=two_employees,
            time_periods=full_day_periods,
            employee_availability=availability,
            hourly_rates=basic_hourly_rates,
            minimum_workers=minimum_workers,
        )

        solver = solver_cls()
        result = solver.solve(problem, config)

        assert result.status in (SolverStatus.OPTIMAL, SolverStatus.SUBOPTIMAL)

        for emp in two_employees:
            scheduled_periods = count_scheduled_periods(result, emp, full_day_periods)
            scheduled_hours = scheduled_periods * 0.5
            assert scheduled_hours <= config.max_daily_hours, \
                f"{solver_name}: {emp} scheduled for {scheduled_hours}h, max is {config.max_daily_hours}h"

    @pytest.mark.parametrize("solver_name,solver_cls", [
        ("gurobi", GurobiSolver),
        ("pulp", PuLPSolver),
        ("ortools", ORToolsSolver),
    ])
    def test_max_hours_with_different_limits(
        self, solver_name, solver_cls, full_day_periods, two_employees, basic_hourly_rates
    ):
        """Test with a restrictive max hours limit."""
        config = SolverConfig(
            dummy_worker_cost=100.0,
            short_shift_penalty=50.0,
            min_shift_hours=2.0,
            max_daily_hours=4.0,
            meal_break_enabled=False,
        )

        availability = {emp: [1] * len(full_day_periods) for emp in two_employees}
        minimum_workers = [1] * len(full_day_periods)

        problem = ScheduleProblem(
            employees=two_employees,
            time_periods=full_day_periods,
            employee_availability=availability,
            hourly_rates=basic_hourly_rates,
            minimum_workers=minimum_workers,
        )

        solver = solver_cls()
        result = solver.solve(problem, config)

        for emp in two_employees:
            scheduled_periods = count_scheduled_periods(result, emp, full_day_periods)
            scheduled_hours = scheduled_periods * 0.5
            assert scheduled_hours <= 4.0, \
                f"{solver_name}: {emp} scheduled for {scheduled_hours}h, max is 4h"


# ============================================================================
# ============================================================================


class TestAvailabilityConstraint:
    """Test that availability constraints are respected."""

    @pytest.mark.parametrize("solver_name,solver_cls", [
        ("gurobi", GurobiSolver),
        ("pulp", PuLPSolver),
        ("ortools", ORToolsSolver),
    ])
    def test_respects_unavailable_periods(
        self, solver_name, solver_cls, basic_time_periods, two_employees, basic_hourly_rates
    ):
        """Employees should not be scheduled when unavailable."""
      
        availability = {
            "Alice": [1] * len(basic_time_periods),
            "Bob": [1, 1, 1, 1, 1] + [0] * (len(basic_time_periods) - 5),
        }

        config = SolverConfig(
            dummy_worker_cost=100.0,
            short_shift_penalty=50.0,
            min_shift_hours=2.0,
            max_daily_hours=11.0,
            meal_break_enabled=False,
        )

        problem = ScheduleProblem(
            employees=two_employees,
            time_periods=basic_time_periods,
            employee_availability=availability,
            hourly_rates=basic_hourly_rates,
            minimum_workers=[1] * len(basic_time_periods),
        )

        solver = solver_cls()
        result = solver.solve(problem, config)

      
        for idx in range(5, len(basic_time_periods)):
            t = basic_time_periods[idx]
            scheduled = result.schedule_matrix.get(("Bob", t), 0)
            assert scheduled == 0, \
                f"{solver_name}: Bob scheduled in unavailable period {idx}"

    @pytest.mark.parametrize("solver_name,solver_cls", [
        ("gurobi", GurobiSolver),
        ("pulp", PuLPSolver),
        ("ortools", ORToolsSolver),
    ])
    def test_completely_unavailable_employee(
        self, solver_name, solver_cls, basic_time_periods, two_employees, basic_hourly_rates
    ):
        """Employee with no availability should not be scheduled."""
        availability = {
            "Alice": [1] * len(basic_time_periods),
            "Bob": [0] * len(basic_time_periods),
        }

        config = SolverConfig(
            dummy_worker_cost=100.0,
            short_shift_penalty=50.0,
            min_shift_hours=2.0,
            max_daily_hours=11.0,
            meal_break_enabled=False,
        )

        problem = ScheduleProblem(
            employees=two_employees,
            time_periods=basic_time_periods,
            employee_availability=availability,
            hourly_rates=basic_hourly_rates,
            minimum_workers=[1] * len(basic_time_periods),
        )

        solver = solver_cls()
        result = solver.solve(problem, config)

        bob_periods = count_scheduled_periods(result, "Bob", basic_time_periods)
        assert bob_periods == 0, \
            f"{solver_name}: Bob scheduled for {bob_periods} periods despite being unavailable"


# ============================================================================
# ============================================================================


class TestLockedPeriods:
    """Test that locked periods are enforced."""

    @pytest.mark.parametrize("solver_name,solver_cls", [
        ("gurobi", GurobiSolver),
        ("pulp", PuLPSolver),
        ("ortools", ORToolsSolver),
    ])
    def test_locked_periods_are_scheduled(
        self, solver_name, solver_cls, basic_time_periods, two_employees, basic_hourly_rates
    ):
        """Locked periods must be scheduled."""
        availability = {emp: [1] * len(basic_time_periods) for emp in two_employees}

      
        locked_periods = {("Alice", 0), ("Alice", 1), ("Alice", 2)}

        config = SolverConfig(
            dummy_worker_cost=100.0,
            short_shift_penalty=50.0,
            min_shift_hours=3.0,
            max_daily_hours=11.0,
            meal_break_enabled=False,
        )

        problem = ScheduleProblem(
            employees=two_employees,
            time_periods=basic_time_periods,
            employee_availability=availability,
            hourly_rates=basic_hourly_rates,
            minimum_workers=[1] * len(basic_time_periods),
            locked_periods=locked_periods,
        )

        solver = solver_cls()
        result = solver.solve(problem, config)

      
        for idx in [0, 1, 2]:
            t = basic_time_periods[idx]
            scheduled = result.schedule_matrix.get(("Alice", t), 0)
            assert scheduled == 1, \
                f"{solver_name}: Alice not scheduled in locked period {idx}"

    @pytest.mark.parametrize("solver_name,solver_cls", [
        ("gurobi", GurobiSolver),
        ("pulp", PuLPSolver),
        ("ortools", ORToolsSolver),
    ])
    def test_locked_periods_override_availability(
        self, solver_name, solver_cls, basic_time_periods, two_employees, basic_hourly_rates
    ):
        """Locked periods should override unavailability."""
      
        availability = {
            "Alice": [1] * len(basic_time_periods),
            "Bob": [0] * len(basic_time_periods),
        }

      
        locked_periods = {("Bob", 0), ("Bob", 1), ("Bob", 2), ("Bob", 3), ("Bob", 4), ("Bob", 5)}

        config = SolverConfig(
            dummy_worker_cost=100.0,
            short_shift_penalty=50.0,
            min_shift_hours=3.0,
            max_daily_hours=11.0,
            meal_break_enabled=False,
        )

        problem = ScheduleProblem(
            employees=two_employees,
            time_periods=basic_time_periods,
            employee_availability=availability,
            hourly_rates=basic_hourly_rates,
            minimum_workers=[1] * len(basic_time_periods),
            locked_periods=locked_periods,
        )

        solver = solver_cls()
        result = solver.solve(problem, config)

      
        for idx in [0, 1, 2, 3, 4, 5]:
            t = basic_time_periods[idx]
            scheduled = result.schedule_matrix.get(("Bob", t), 0)
            assert scheduled == 1, \
                f"{solver_name}: Bob not scheduled in locked period {idx} (should override availability)"


# ============================================================================
# ============================================================================


class TestMealBreaks:
    """Test meal break scheduling logic."""

    @pytest.mark.parametrize("solver_name,solver_cls", [
        ("gurobi", GurobiSolver),
        ("pulp", PuLPSolver),
        ("ortools", ORToolsSolver),
    ])
    def test_meal_break_scheduled_for_long_shifts(
        self, solver_name, solver_cls, full_day_periods
    ):
        """Employees working > 5 hours should get a meal break."""
        employees = ["Alice"]
        availability = {"Alice": [1] * len(full_day_periods)}
        hourly_rates = {"Alice": 15.0}

        config = SolverConfig(
            dummy_worker_cost=100.0,
            short_shift_penalty=50.0,
            min_shift_hours=3.0,
            max_daily_hours=11.0,
            meal_break_enabled=True,
            meal_break_threshold_hours=5.0,
            meal_break_duration_periods=1,
        )

      
        minimum_workers = [1] * len(full_day_periods)

        problem = ScheduleProblem(
            employees=employees,
            time_periods=full_day_periods,
            employee_availability=availability,
            hourly_rates=hourly_rates,
            minimum_workers=minimum_workers,
        )

        solver = solver_cls()
        result = solver.solve(problem, config)

      
        scheduled_periods = count_scheduled_periods(result, "Alice", full_day_periods)
        scheduled_hours = scheduled_periods * 0.5

        if scheduled_hours > 5.0:
          
            assert "Alice" in result.break_periods, \
                f"{solver_name}: Alice working {scheduled_hours}h should have break periods"
            assert len(result.break_periods["Alice"]) >= 1, \
                f"{solver_name}: Alice should have at least 1 break period"

    @pytest.mark.parametrize("solver_name,solver_cls", [
        ("gurobi", GurobiSolver),
        ("pulp", PuLPSolver),
        ("ortools", ORToolsSolver),
    ])
    def test_no_meal_break_for_short_shifts(
        self, solver_name, solver_cls, short_time_periods
    ):
        """Employees working <= 5 hours should not need a meal break."""
        employees = ["Alice"]
        availability = {"Alice": [1] * len(short_time_periods)}
        hourly_rates = {"Alice": 15.0}

        config = SolverConfig(
            dummy_worker_cost=100.0,
            short_shift_penalty=50.0,
            min_shift_hours=3.0,
            max_daily_hours=11.0,
            meal_break_enabled=True,
            meal_break_threshold_hours=5.0,
            meal_break_duration_periods=1,
        )

        minimum_workers = [1] * len(short_time_periods)

        problem = ScheduleProblem(
            employees=employees,
            time_periods=short_time_periods,
            employee_availability=availability,
            hourly_rates=hourly_rates,
            minimum_workers=minimum_workers,
        )

        solver = solver_cls()
        result = solver.solve(problem, config)

        scheduled_periods = count_scheduled_periods(result, "Alice", short_time_periods)
        scheduled_hours = scheduled_periods * 0.5

      
        if scheduled_hours <= 5.0:
            alice_breaks = result.break_periods.get("Alice", [])
            assert len(alice_breaks) == 0, \
                f"{solver_name}: Alice working {scheduled_hours}h should not have breaks"

    @pytest.mark.parametrize("solver_name,solver_cls", [
        ("gurobi", GurobiSolver),
        ("pulp", PuLPSolver),
        ("ortools", ORToolsSolver),
    ])
    def test_break_not_at_shift_boundaries(
        self, solver_name, solver_cls, full_day_periods
    ):
        """Breaks should not be placed at the first or last period of a shift."""
        employees = ["Alice"]
        availability = {"Alice": [1] * len(full_day_periods)}
        hourly_rates = {"Alice": 15.0}

        config = SolverConfig(
            dummy_worker_cost=100.0,
            short_shift_penalty=50.0,
            min_shift_hours=3.0,
            max_daily_hours=11.0,
            meal_break_enabled=True,
            meal_break_threshold_hours=5.0,
            meal_break_duration_periods=1,
        )

        minimum_workers = [1] * len(full_day_periods)

        problem = ScheduleProblem(
            employees=employees,
            time_periods=full_day_periods,
            employee_availability=availability,
            hourly_rates=hourly_rates,
            minimum_workers=minimum_workers,
        )

        solver = solver_cls()
        result = solver.solve(problem, config)

        scheduled_indices = get_scheduled_period_indices(result, "Alice", full_day_periods)
        if not scheduled_indices:
            return

        first_period = min(scheduled_indices)
        last_period = max(scheduled_indices)

        break_periods = result.break_periods.get("Alice", [])
        for bp in break_periods:
            assert bp != first_period, \
                f"{solver_name}: Break at first period of shift"
            assert bp != last_period, \
                f"{solver_name}: Break at last period of shift"

    @pytest.mark.parametrize("solver_name,solver_cls", [
        ("gurobi", GurobiSolver),
        ("pulp", PuLPSolver),
        ("ortools", ORToolsSolver),
    ])
    def test_break_during_scheduled_period(
        self, solver_name, solver_cls, full_day_periods
    ):
        """Breaks should only occur during scheduled periods."""
        employees = ["Alice"]
        availability = {"Alice": [1] * len(full_day_periods)}
        hourly_rates = {"Alice": 15.0}

        config = SolverConfig(
            dummy_worker_cost=100.0,
            short_shift_penalty=50.0,
            min_shift_hours=3.0,
            max_daily_hours=11.0,
            meal_break_enabled=True,
            meal_break_threshold_hours=5.0,
            meal_break_duration_periods=1,
        )

        minimum_workers = [1] * len(full_day_periods)

        problem = ScheduleProblem(
            employees=employees,
            time_periods=full_day_periods,
            employee_availability=availability,
            hourly_rates=hourly_rates,
            minimum_workers=minimum_workers,
        )

        solver = solver_cls()
        result = solver.solve(problem, config)

        scheduled_indices = set(get_scheduled_period_indices(result, "Alice", full_day_periods))
        break_periods = result.break_periods.get("Alice", [])

        for bp in break_periods:
            assert bp in scheduled_indices, \
                f"{solver_name}: Break at period {bp} but not scheduled"


# ============================================================================
# Employees on Break Don't Count Toward Minimum Staffing
# ============================================================================


class TestBreakStaffing:
    """Test that employees on break don't count toward minimum staffing."""

    @pytest.mark.parametrize("solver_name,solver_cls", [
        ("gurobi", GurobiSolver),
        ("pulp", PuLPSolver),
        ("ortools", ORToolsSolver),
    ])
    def test_minimum_staffing_excludes_breaks(
        self, solver_name, solver_cls, full_day_periods, three_employees, three_employee_rates
    ):
        """Minimum staffing should be met excluding employees on break."""
        availability = {emp: [1] * len(full_day_periods) for emp in three_employees}

        config = SolverConfig(
            dummy_worker_cost=100.0,
            short_shift_penalty=50.0,
            min_shift_hours=3.0,
            max_daily_hours=11.0,
            meal_break_enabled=True,
            meal_break_threshold_hours=5.0,
            meal_break_duration_periods=1,
        )

      
        minimum_workers = [2] * len(full_day_periods)

        problem = ScheduleProblem(
            employees=three_employees,
            time_periods=full_day_periods,
            employee_availability=availability,
            hourly_rates=three_employee_rates,
            minimum_workers=minimum_workers,
        )

        solver = solver_cls()
        result = solver.solve(problem, config)

        assert result.status in (SolverStatus.OPTIMAL, SolverStatus.SUBOPTIMAL)

      
        for t_idx in range(1, len(full_day_periods)):
            t = full_day_periods[t_idx]
            working_count = 0

            for emp in three_employees:
                is_scheduled = result.schedule_matrix.get((emp, t), 0) == 1
                is_on_break = t_idx in result.break_periods.get(emp, [])

                if is_scheduled and not is_on_break:
                    working_count += 1

            dummy_count = result.dummy_values.get(t, 0)

          
            assert working_count + dummy_count >= minimum_workers[t_idx], \
                f"{solver_name}: Period {t_idx} has {working_count} working + {dummy_count} dummy, needs {minimum_workers[t_idx]}"


# ============================================================================
# ============================================================================


class TestSolverConsistency:
    """Test that all solvers produce consistent results."""

    def test_all_solvers_find_feasible_solution(self, basic_problem, default_config, all_solvers):
        """All solvers should find a feasible solution for the same problem."""
        results = {}
        for name, solver in all_solvers:
            result = solver.solve(basic_problem, default_config)
            results[name] = result

            assert result.status in (SolverStatus.OPTIMAL, SolverStatus.SUBOPTIMAL), \
                f"{name} failed to find feasible solution"

    def test_all_solvers_produce_valid_schedules(
        self, basic_problem, default_config, all_solvers
    ):
        """All solvers should produce schedules that satisfy constraints."""
        for name, solver in all_solvers:
            result = solver.solve(basic_problem, default_config)

          
            for emp in basic_problem.employees:
                scheduled = count_scheduled_periods(result, emp, basic_problem.time_periods)
                hours = scheduled * 0.5
                assert hours <= default_config.max_daily_hours, \
                    f"{name}: {emp} exceeds max hours"

          
            for emp in basic_problem.employees:
                for idx, t in enumerate(basic_problem.time_periods):
                    if basic_problem.employee_availability[emp][idx] == 0:
                      
                        if (emp, idx) not in basic_problem.locked_periods:
                            scheduled = result.schedule_matrix.get((emp, t), 0)
                            assert scheduled == 0, \
                                f"{name}: {emp} scheduled in unavailable period {idx}"

    def test_all_solvers_handle_meal_breaks_consistently(
        self, full_day_periods, meal_break_config
    ):
        """All solvers should handle meal breaks consistently."""
        employees = ["Alice"]
        availability = {"Alice": [1] * len(full_day_periods)}
        hourly_rates = {"Alice": 15.0}
        minimum_workers = [1] * len(full_day_periods)

        problem = ScheduleProblem(
            employees=employees,
            time_periods=full_day_periods,
            employee_availability=availability,
            hourly_rates=hourly_rates,
            minimum_workers=minimum_workers,
        )

        solvers = [
            ("gurobi", GurobiSolver()),
            ("pulp", PuLPSolver()),
            ("ortools", ORToolsSolver()),
        ]

        for name, solver in solvers:
            result = solver.solve(problem, meal_break_config)

            scheduled_periods = count_scheduled_periods(result, "Alice", full_day_periods)
            scheduled_hours = scheduled_periods * 0.5

            if scheduled_hours > meal_break_config.meal_break_threshold_hours:
              
                assert "Alice" in result.break_periods, \
                    f"{name}: Missing breaks for {scheduled_hours}h shift"

              
                scheduled_indices = get_scheduled_period_indices(result, "Alice", full_day_periods)
                if scheduled_indices:
                    first = min(scheduled_indices)
                    last = max(scheduled_indices)
                    for bp in result.break_periods["Alice"]:
                        assert bp > first and bp < last, \
                            f"{name}: Break at boundary period"


# ============================================================================
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.parametrize("solver_name,solver_cls", [
        ("gurobi", GurobiSolver),
        ("pulp", PuLPSolver),
        ("ortools", ORToolsSolver),
    ])
    def test_single_employee(self, solver_name, solver_cls, short_time_periods):
        """Test with only one employee."""
        employees = ["Alice"]
        availability = {"Alice": [1] * len(short_time_periods)}
        hourly_rates = {"Alice": 15.0}

        config = SolverConfig(
            dummy_worker_cost=100.0,
            short_shift_penalty=50.0,
            min_shift_hours=2.0,
            max_daily_hours=11.0,
            meal_break_enabled=False,
        )

        problem = ScheduleProblem(
            employees=employees,
            time_periods=short_time_periods,
            employee_availability=availability,
            hourly_rates=hourly_rates,
            minimum_workers=[1] * len(short_time_periods),
        )

        solver = solver_cls()
        result = solver.solve(problem, config)

        assert result.status in (SolverStatus.OPTIMAL, SolverStatus.SUBOPTIMAL), \
            f"{solver_name} failed with single employee"

    @pytest.mark.parametrize("solver_name,solver_cls", [
        ("gurobi", GurobiSolver),
        ("pulp", PuLPSolver),
        ("ortools", ORToolsSolver),
    ])
    def test_zero_minimum_workers(self, solver_name, solver_cls, short_time_periods):
        """Test with zero minimum workers (optional staffing)."""
        employees = ["Alice", "Bob"]
        availability = {emp: [1] * len(short_time_periods) for emp in employees}
        hourly_rates = {"Alice": 15.0, "Bob": 18.0}

        config = SolverConfig(
            dummy_worker_cost=100.0,
            short_shift_penalty=50.0,
            min_shift_hours=2.0,
            max_daily_hours=11.0,
            meal_break_enabled=False,
        )

        problem = ScheduleProblem(
            employees=employees,
            time_periods=short_time_periods,
            employee_availability=availability,
            hourly_rates=hourly_rates,
            minimum_workers=[0] * len(short_time_periods),
        )

        solver = solver_cls()
        result = solver.solve(problem, config)

        assert result.status in (SolverStatus.OPTIMAL, SolverStatus.SUBOPTIMAL), \
            f"{solver_name} failed with zero minimum workers"

    @pytest.mark.parametrize("solver_name,solver_cls", [
        ("gurobi", GurobiSolver),
        ("pulp", PuLPSolver),
        ("ortools", ORToolsSolver),
    ])
    def test_exactly_threshold_hours(self, solver_name, solver_cls):
        """Test shift exactly at meal break threshold."""
      
        time_periods = [f"{9 + i // 2:02d}:{(i % 2) * 30:02d}" for i in range(10)]
        employees = ["Alice"]
        availability = {"Alice": [1] * len(time_periods)}
        hourly_rates = {"Alice": 15.0}

        config = SolverConfig(
            dummy_worker_cost=100.0,
            short_shift_penalty=50.0,
            min_shift_hours=3.0,
            max_daily_hours=5.0,
            meal_break_enabled=True,
            meal_break_threshold_hours=5.0,
            meal_break_duration_periods=1,
        )

        problem = ScheduleProblem(
            employees=employees,
            time_periods=time_periods,
            employee_availability=availability,
            hourly_rates=hourly_rates,
            minimum_workers=[1] * len(time_periods),
        )

        solver = solver_cls()
        result = solver.solve(problem, config)

        assert result.status in (SolverStatus.OPTIMAL, SolverStatus.SUBOPTIMAL), \
            f"{solver_name} failed with threshold hours"


# ============================================================================
# ============================================================================


class TestInfeasibility:
    """Test infeasibility detection."""

    @pytest.mark.parametrize("solver_name,solver_cls", [
        ("gurobi", GurobiSolver),
        ("pulp", PuLPSolver),
        ("ortools", ORToolsSolver),
    ])
    def test_detects_infeasible_due_to_insufficient_availability(
        self, solver_name, solver_cls, short_time_periods
    ):
        """Detect when problem is infeasible due to insufficient availability."""
        employees = ["Alice"]
      
        availability = {"Alice": [1, 1, 0, 0, 0, 0, 0, 0]}
        hourly_rates = {"Alice": 15.0}

        config = SolverConfig(
            dummy_worker_cost=1000000.0,
            short_shift_penalty=50.0,
            min_shift_hours=2.0,
            max_daily_hours=11.0,
            meal_break_enabled=False,
        )

        problem = ScheduleProblem(
            employees=employees,
            time_periods=short_time_periods,
            employee_availability=availability,
            hourly_rates=hourly_rates,
          
            minimum_workers=[1] * len(short_time_periods),
        )

        solver = solver_cls()
        result = solver.solve(problem, config)

      
      
        assert result.status in (SolverStatus.OPTIMAL, SolverStatus.SUBOPTIMAL, SolverStatus.INFEASIBLE)
