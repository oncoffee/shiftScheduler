from pydantic import BaseModel
from datetime import datetime


class ShiftPeriod(BaseModel):
    period_index: int
    start_time: str
    end_time: str
    scheduled: bool
    is_locked: bool = False
    is_break: bool = False


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


class ComplianceViolationSchema(BaseModel):
    """Compliance violation detected in schedule."""
    rule_type: str  # "MINOR_CURFEW", "REST_VIOLATION", "OVERTIME", etc.
    severity: str  # "error", "warning"
    employee_name: str
    date: str | None = None
    message: str
    details: dict | None = None


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
    compliance_violations: list[ComplianceViolationSchema] = []


class ShiftUpdateRequest(BaseModel):
    employee_name: str
    day_of_week: str
    date: str | None = None
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


# ============================================================================
# New Assignments API Response Models
# ============================================================================

from typing import Literal


AssignmentSourceType = Literal["solver", "manual"]
EditTypeValue = Literal["create", "update", "delete", "lock", "unlock"]


class AssignmentResponse(BaseModel):
    """Response model for a single assignment."""
    id: str
    employee_name: str
    date: str
    day_of_week: str
    store_name: str
    shift_start: str | None
    shift_end: str | None
    total_hours: float
    is_short_shift: bool
    is_locked: bool
    source: AssignmentSourceType
    periods: list[ShiftPeriod]
    created_at: str
    updated_at: str
    solver_run_id: str | None


class AssignmentListResponse(BaseModel):
    """Response model for paginated assignment list."""
    items: list[AssignmentResponse]
    total: int
    limit: int
    offset: int


class DailySummaryResponse(BaseModel):
    """Response model for a daily summary."""
    id: str
    store_name: str
    date: str
    day_of_week: str
    total_cost: float
    employees_scheduled: int
    total_labor_hours: float
    dummy_worker_cost: float
    short_shift_penalty: float
    unfilled_periods: list[UnfilledPeriod]
    compliance_violations: list[ComplianceViolationSchema]
    created_at: str
    updated_at: str


class DailySummaryListResponse(BaseModel):
    """Response model for paginated daily summary list."""
    items: list[DailySummaryResponse]
    total: int
    limit: int
    offset: int


class AssignmentUpdateResponse(BaseModel):
    """Response model for assignment update."""
    success: bool
    assignment: AssignmentResponse


class AssignmentDeleteResponse(BaseModel):
    """Response model for assignment deletion."""
    success: bool
    deleted_id: str


class AssignmentEditResponse(BaseModel):
    """Response model for assignment edit audit record."""
    id: str
    assignment_id: str | None
    employee_name: str
    date: str
    store_name: str
    edit_type: EditTypeValue
    previous_values: dict | None
    new_values: dict | None
    edited_at: str
    edited_by: str | None


class AssignmentEditListResponse(BaseModel):
    """Response model for paginated assignment edit list."""
    items: list[AssignmentEditResponse]
    total: int
    limit: int
    offset: int
