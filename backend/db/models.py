from datetime import datetime
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "employees"


class StoreHours(BaseModel):
    week_no: int
    day_of_week: str
    start_time: str
    end_time: str


class StoreDoc(Document):
    store_name: Indexed(str, unique=True)
    hours: list[StoreHours] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "stores"


class ConfigDoc(Document):
    dummy_worker_cost: float = 100.0
    short_shift_penalty: float = 50.0
    min_shift_hours: float = 3.0
    max_daily_hours: float = 11.0
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "config"


class ShiftPeriodEmbed(BaseModel):
    period_index: int
    start_time: str
    end_time: str
    scheduled: bool


class Assignment(BaseModel):
    employee_name: str
    day_of_week: str
    total_hours: float
    shift_start: Optional[str] = None
    shift_end: Optional[str] = None
    is_short_shift: bool = False
    periods: list[ShiftPeriodEmbed] = []


class UnfilledPeriodEmbed(BaseModel):
    period_index: int
    start_time: str
    end_time: str
    workers_needed: int


class DailySummary(BaseModel):
    day_of_week: str
    total_cost: float
    employees_scheduled: int
    total_labor_hours: float
    dummy_worker_cost: float = 0
    unfilled_periods: list[UnfilledPeriodEmbed] = []


class ScheduleRunDoc(Document):
    week_no: int
    store_name: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_weekly_cost: float
    total_dummy_worker_cost: float = 0
    total_short_shift_penalty: float = 0
    status: str
    has_warnings: bool = False
    is_current: bool = False
    daily_summaries: list[DailySummary] = []
    assignments: list[Assignment] = []

    class Settings:
        name = "schedule_runs"
        indexes = [
            [("generated_at", -1)],
            [("week_no", 1), ("store_name", 1)],
            [("is_current", 1)],
        ]
