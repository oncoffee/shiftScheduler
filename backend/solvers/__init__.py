"""Multi-solver architecture for shift scheduling optimization."""

from .types import (
    SolverType,
    SolverStatus,
    SolverConfig,
    ScheduleProblem,
    SolverResult,
)
from .base import ShiftSchedulerSolver
from .gurobi_solver import GurobiSolver
from .pulp_solver import PuLPSolver
from .ortools_solver import ORToolsSolver


def create_solver(solver_type: SolverType | str) -> ShiftSchedulerSolver:
    """
    Factory function to create a solver instance.

    Args:
        solver_type: The type of solver to create (SolverType enum or string)

    Returns:
        A solver instance implementing ShiftSchedulerSolver protocol

    Raises:
        ValueError: If solver_type is not recognized
    """
    if isinstance(solver_type, str):
        solver_type = SolverType(solver_type.lower())

    if solver_type == SolverType.GUROBI:
        return GurobiSolver()
    elif solver_type == SolverType.PULP:
        return PuLPSolver()
    elif solver_type == SolverType.ORTOOLS:
        return ORToolsSolver()
    else:
        raise ValueError(f"Unknown solver type: {solver_type}")


__all__ = [
    "SolverType",
    "SolverStatus",
    "SolverConfig",
    "ScheduleProblem",
    "SolverResult",
    "ShiftSchedulerSolver",
    "GurobiSolver",
    "PuLPSolver",
    "ORToolsSolver",
    "create_solver",
]
