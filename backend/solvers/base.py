"""Base protocol for shift scheduler solvers."""

from typing import Protocol

from .types import ScheduleProblem, SolverConfig, SolverResult


class ShiftSchedulerSolver(Protocol):
    """Protocol defining the interface for shift scheduling solvers."""

    def solve(
        self,
        problem: ScheduleProblem,
        config: SolverConfig,
    ) -> SolverResult:
        """
        Solve the shift scheduling problem.

        Args:
            problem: The scheduling problem definition
            config: Solver configuration parameters

        Returns:
            SolverResult with status, objective, and schedule
        """
        ...

    def write_model(self, filename: str) -> None:
        """
        Write the model to a file for debugging.

        Args:
            filename: Path to write the model file
        """
        ...

    def compute_iis(self, filename: str) -> None:
        """
        Compute and write the Irreducible Inconsistent Subsystem.

        Only applicable when model is infeasible.

        Args:
            filename: Path to write the IIS file
        """
        ...
