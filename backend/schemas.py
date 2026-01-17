from pydantic import BaseModel
from datetime import datetime


class ShiftPeriod(BaseModel):
    period_index: int
    start_time: str
    end_time: str
    scheduled: bool
    is_locked: bool = False


class EmployeeDaySchedule(BaseModel):
    employee_name: str
    day_of_week: str
    date: str | None = None  # ISO date string: "2025-01-20"
    periods: list[ShiftPeriod]
    total_hours: float
    shift_start: str | None
    shift_end: str | None
    is_short_shift: bool = False
    is_locked: bool = False


class UnfilledPeriod(BaseModel):
    period_index: int
    start_time: str
    end_time: str
    workers_needed: int


class DayScheduleSummary(BaseModel):
    day_of_week: str
    date: str | None = None  # ISO date string: "2025-01-20"
    total_cost: float
    employees_scheduled: int
    total_labor_hours: float
    unfilled_periods: list[UnfilledPeriod] = []
    dummy_worker_cost: float = 0


class WeeklyScheduleResult(BaseModel):
    start_date: str  # ISO date string: "2025-01-20"
    end_date: str    # ISO date string: "2025-01-26"
    store_name: str
    generated_at: str
    schedules: list[EmployeeDaySchedule]
    daily_summaries: list[DayScheduleSummary]
    total_weekly_cost: float
    status: str
    total_dummy_worker_cost: float = 0
    total_short_shift_penalty: float = 0
    has_warnings: bool = False
    is_edited: bool = False
    last_edited_at: str | None = None


class ShiftUpdateRequest(BaseModel):
    employee_name: str
    day_of_week: str
    new_shift_start: str
    new_shift_end: str
    new_employee_name: str | None = None


class ShiftUpdateResponse(BaseModel):
    success: bool
    updated_schedule: WeeklyScheduleResult
    recalculated_cost: float


class ValidationError(BaseModel):
    code: str
    message: str


class ValidationWarning(BaseModel):
    code: str
    message: str


class ValidateChangeRequest(BaseModel):
    employee_name: str
    day_of_week: str
    proposed_start: str
    proposed_end: str


class ValidateChangeResponse(BaseModel):
    is_valid: bool
    errors: list[ValidationError] = []
    warnings: list[ValidationWarning] = []


class BatchUpdateRequest(BaseModel):
    updates: list[ShiftUpdateRequest]


class BatchUpdateResponse(BaseModel):
    success: bool
    updated_schedule: WeeklyScheduleResult
    recalculated_cost: float
    failed_updates: list[dict] = []


class ToggleLockRequest(BaseModel):
    employee_name: str
    date: str
    is_locked: bool


class ToggleLockResponse(BaseModel):
    success: bool
    updated_schedule: WeeklyScheduleResult
