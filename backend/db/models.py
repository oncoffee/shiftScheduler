from datetime import datetime, date
from typing import Optional
from beanie import Document, Indexed
from pydantic import BaseModel, Field


class AvailabilitySlot(BaseModel):
    day_of_week: str
    start_time: str
    end_time: str


class EmployeeDoc(Document):
    employee_name: Indexed(str, unique=True)
    hourly_rate: float
    minimum_hours_per_week: int
    minimum_hours: int
    maximum_hours: int
    disabled: bool = False
    availability: list[AvailabilitySlot] = []
    # Compliance fields
    date_of_birth: Optional[date] = None
    is_minor: bool = False  # Auto-calculated from DOB or manual override
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "employees"


class StoreHours(BaseModel):
    day_of_week: str
    start_time: str
    end_time: str


class StaffingRequirement(BaseModel):
    day_type: str
    start_time: str
    end_time: str
    min_staff: int


class StoreDoc(Document):
    store_name: Indexed(str, unique=True)
    hours: list[StoreHours] = []
    staffing_requirements: list[StaffingRequirement] = []
    # Compliance fields
    jurisdiction: str = "DEFAULT"  # "CA", "NY", "TX", etc. for state-specific rules
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "stores"


class ConfigDoc(Document):
    dummy_worker_cost: float = 100.0
    short_shift_penalty: float = 50.0
    min_shift_hours: float = 3.0
    max_daily_hours: float = 11.0
    solver_type: str = "gurobi"
    # Compliance settings
    compliance_mode: str = "warn"  # "off", "warn", "enforce"
    enable_rest_between_shifts: bool = True
    enable_minor_restrictions: bool = True
    enable_overtime_tracking: bool = True
    enable_break_compliance: bool = True
    enable_predictive_scheduling: bool = True
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "config"


class ShiftPeriodEmbed(BaseModel):
    period_index: int
    start_time: str
    end_time: str
    scheduled: bool
    is_locked: bool = False
    is_break: bool = False


class Assignment(BaseModel):
    employee_name: str
    day_of_week: str
    date: Optional[str] = None  # ISO date string: "2025-01-20"
    total_hours: float
    shift_start: Optional[str] = None
    shift_end: Optional[str] = None
    is_short_shift: bool = False
    is_locked: bool = False
    periods: list[ShiftPeriodEmbed] = []


class UnfilledPeriodEmbed(BaseModel):
    period_index: int
    start_time: str
    end_time: str
    workers_needed: int


class DailySummary(BaseModel):
    day_of_week: str
    date: Optional[str] = None  # ISO date string: "2025-01-20"
    total_cost: float
    employees_scheduled: int
    total_labor_hours: float
    dummy_worker_cost: float = 0
    unfilled_periods: list[UnfilledPeriodEmbed] = []


class ComplianceViolation(BaseModel):
    """A compliance violation detected in a schedule."""
    rule_type: str  # "MINOR_CURFEW", "REST_VIOLATION", "OVERTIME", "BREAK_REQUIRED", "PREDICTIVE_NOTICE"
    severity: str  # "error", "warning"
    employee_name: str
    date: Optional[str] = None  # ISO date string
    message: str
    details: Optional[dict] = None  # Additional context (e.g., hours worked, threshold exceeded)


class ScheduleRunDoc(Document):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    store_name: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_weekly_cost: float
    total_dummy_worker_cost: float = 0
    total_short_shift_penalty: float = 0
    status: str
    has_warnings: bool = False
    is_current: bool = False
    is_edited: bool = False
    last_edited_at: Optional[datetime] = None
    published_at: Optional[datetime] = None  # For predictive scheduling compliance
    daily_summaries: list[DailySummary] = []
    assignments: list[Assignment] = []
    compliance_violations: list[ComplianceViolation] = []  # Labor law compliance violations

    class Settings:
        name = "schedule_runs"
        indexes = [
            [("generated_at", -1)],
            [("start_date", 1), ("end_date", 1), ("store_name", 1)],
            [("is_current", 1)],
        ]


class ComplianceRuleDoc(Document):
    """Jurisdiction-specific compliance rules for labor law enforcement."""
    jurisdiction: Indexed(str, unique=True)  # "CA", "NY", "DEFAULT", etc.

    # Rest between shifts (anti-clopening)
    min_rest_hours: float = 8.0

    # Minor restrictions
    minor_max_daily_hours: float = 8.0
    minor_max_weekly_hours: float = 40.0
    minor_curfew_end: str = "22:00"  # Minors cannot work after this time
    minor_earliest_start: str = "06:00"  # Minors cannot work before this time
    minor_age_threshold: int = 18  # Age below which employee is considered minor

    # Overtime thresholds
    daily_overtime_threshold: Optional[float] = None  # e.g., 8.0 for CA daily OT
    weekly_overtime_threshold: float = 40.0

    # Break requirements
    meal_break_after_hours: float = 5.0  # Hours worked before meal break required
    meal_break_duration_minutes: int = 30
    rest_break_interval_hours: float = 4.0  # Hours between rest breaks
    rest_break_duration_minutes: int = 10

    # Predictive scheduling
    advance_notice_days: int = 14  # Days notice required before schedule published

    # Metadata
    source: Optional[str] = None  # "AI_SUGGESTED", "MANUAL", "DEFAULT"
    ai_sources: list[str] = []  # Citations from AI research
    notes: Optional[str] = None  # Important caveats or exceptions
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "compliance_rules"


class ComplianceRuleSuggestion(BaseModel):
    """AI-suggested compliance rules pending human approval."""
    suggestion_id: str
    jurisdiction: str
    min_rest_hours: Optional[float] = None
    minor_curfew_end: Optional[str] = None
    minor_earliest_start: Optional[str] = None
    minor_max_daily_hours: Optional[float] = None
    minor_max_weekly_hours: Optional[float] = None
    daily_overtime_threshold: Optional[float] = None
    weekly_overtime_threshold: Optional[float] = None
    meal_break_after_hours: Optional[float] = None
    meal_break_duration_minutes: Optional[int] = None
    rest_break_interval_hours: Optional[float] = None
    rest_break_duration_minutes: Optional[int] = None
    advance_notice_days: Optional[int] = None
    sources: list[str] = []  # Citation URLs or references
    notes: Optional[str] = None  # Important caveats
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ComplianceRuleEdit(BaseModel):
    """A single field edit in the audit trail."""
    field_name: str
    original_value: Optional[str] = None  # String representation of original
    edited_value: Optional[str] = None  # String representation of edited


class ComplianceAuditDoc(Document):
    """
    Audit trail for compliance rule changes.
    Tracks what AI suggested, what human edited, and final approved values.
    Critical for legal protection and compliance verification.
    """
    # Reference info
    jurisdiction: str
    suggestion_id: str  # Links to original AI suggestion

    # Original AI suggestion (full snapshot)
    ai_original: dict = {}  # Full original suggestion as dict
    ai_model_used: str = ""
    ai_confidence_level: str = ""  # "low", "medium", "high"
    ai_sources: list[str] = []
    ai_validation_warnings: list[str] = []
    ai_disclaimer: str = ""

    # Human edits (what was changed)
    human_edits: list[ComplianceRuleEdit] = []  # List of field changes
    edit_count: int = 0  # Number of fields modified

    # Final approved values (full snapshot)
    approved_values: dict = {}

    # Approval metadata
    approved_at: datetime = Field(default_factory=datetime.utcnow)
    approved_by: Optional[str] = None  # User identifier if auth is implemented
    approval_notes: Optional[str] = None  # Optional notes from approver

    # Session info for traceability
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    class Settings:
        name = "compliance_audit"
        indexes = [
            [("jurisdiction", 1)],
            [("approved_at", -1)],
            [("suggestion_id", 1)],
        ]
