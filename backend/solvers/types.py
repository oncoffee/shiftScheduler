"""Type definitions for the multi-solver architecture."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SolverType(str, Enum):
    """Available solver types."""
    GUROBI = "gurobi"
    PULP = "pulp"
    ORTOOLS = "ortools"


class SolverStatus(str, Enum):
    """Solver result status."""
    OPTIMAL = "optimal"
    SUBOPTIMAL = "suboptimal"
    INFEASIBLE = "infeasible"
    ERROR = "error"


@dataclass
class SolverConfig:
    """Configuration parameters for the solver."""
    dummy_worker_cost: float = 100.0
    short_shift_penalty: float = 50.0
    min_shift_hours: float = 3.0
    max_daily_hours: float = 11.0
    meal_break_enabled: bool = True
    meal_break_threshold_hours: float = 5.0
    meal_break_duration_periods: int = 1


@dataclass
class ScheduleProblem:
    """Input data for the scheduling problem."""
    employees: list[str]
    time_periods: list[str]
    employee_availability: dict[str, list[int]]
    hourly_rates: dict[str, float]
    minimum_workers: list[int]
    locked_periods: set[tuple[str, int]] = field(default_factory=set)
    # Compliance fields
    employee_is_minor: dict[str, bool] = field(default_factory=dict)
    minor_curfew_period: int | None = None  # Period index after which minors cannot work
    minor_earliest_period: int | None = None  # Period index before which minors cannot work
    rest_blocked_periods: dict[str, set[int]] = field(default_factory=dict)  # Blocked due to rest requirements


@dataclass
class SolverResult:
    """Result from a solver run."""
    status: SolverStatus
    objective_value: float
    schedule_matrix: dict[tuple[str, str], int]  # (employee, period) -> 0 or 1
    dummy_values: dict[str, float]  # period -> dummy worker count
    short_shift_hours: dict[str, float]  # employee -> short shift penalty hours
    break_periods: dict[str, list[int]] = field(default_factory=dict)  # employee -> list of break period indices
    solve_time: float = 0.0
    model_file: str | None = None
    iis_file: str | None = None
