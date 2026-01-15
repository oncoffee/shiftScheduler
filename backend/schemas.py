from pydantic import BaseModel
from datetime import datetime


class ShiftPeriod(BaseModel):
    """Single 30-minute time period within a shift"""
    period_index: int
    start_time: str  # "09:00"
    end_time: str    # "09:30"
    scheduled: bool


class EmployeeDaySchedule(BaseModel):
    """One employee's schedule for one day"""
    employee_name: str
    day_of_week: str
    periods: list[ShiftPeriod]
    total_hours: float
    shift_start: str | None  # First scheduled period time
    shift_end: str | None    # Last scheduled period end time
    is_short_shift: bool = False  # True if below minimum hours


class UnfilledPeriod(BaseModel):
    """A time period that needs manual assignment"""
    period_index: int
    start_time: str
    end_time: str
    workers_needed: int


class DayScheduleSummary(BaseModel):
    """Summary for one day"""
    day_of_week: str
    total_cost: float
    employees_scheduled: int
    total_labor_hours: float
    unfilled_periods: list[UnfilledPeriod] = []  # Periods needing manual assignment
    dummy_worker_cost: float = 0  # Penalty cost from unfilled shifts


class WeeklyScheduleResult(BaseModel):
    """Complete schedule result from solver"""
    week_no: int
    store_name: str
    generated_at: str
    schedules: list[EmployeeDaySchedule]
    daily_summaries: list[DayScheduleSummary]
    total_weekly_cost: float
    status: str  # "optimal", "feasible", "infeasible"
    total_dummy_worker_cost: float = 0  # Total penalty from unfilled shifts
    total_short_shift_penalty: float = 0  # Total penalty from short shifts
    has_warnings: bool = False  # True if dummy workers or short shifts exist
