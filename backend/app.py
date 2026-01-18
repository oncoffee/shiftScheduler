import os
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from model_run import main
import data_import
from schemas import (
    WeeklyScheduleResult,
    ShiftUpdateRequest,
    ShiftUpdateResponse,
    ValidateChangeRequest,
    ValidateChangeResponse,
    ValidationError as ValidationErrorSchema,
    ValidationWarning as ValidationWarningSchema,
    BatchUpdateRequest,
    BatchUpdateResponse,
    ToggleLockRequest,
    ToggleLockResponse,
)
from cost_calculator import (
    validate_schedule_change,
    recalculate_schedule_costs,
    update_assignment_times,
    get_config as get_solver_config,
)
from db import (
    init_db,
    EmployeeDoc,
    StoreDoc,
    ConfigDoc,
    ScheduleRunDoc,
    sync_all_from_sheets,
    Assignment,
    DailySummary,
    UnfilledPeriodEmbed,
    ShiftPeriodEmbed,
    ComplianceRuleDoc,
    ComplianceViolation,
)
from db.database import close_db
from db.models import StoreHours

load_dotenv()

SOLVER_PASS_KEY = os.getenv("SOLVER_PASS_KEY", "changeme")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


async def get_staffing_requirements() -> list[dict] | None:
    stores = await StoreDoc.find().to_list()
    if stores and stores[0].staffing_requirements:
        return [
            {
                "day_type": r.day_type,
                "start_time": normalize_time(r.start_time),
                "end_time": normalize_time(r.end_time),
                "min_staff": r.min_staff,
            }
            for r in stores[0].staffing_requirements
        ]
    return None


app = FastAPI(title="shiftScheduler", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/sync/all")
async def sync_all(pass_key: str):
    if pass_key != SOLVER_PASS_KEY:
        raise HTTPException(status_code=422, detail="Invalid Credentials")

    result = await sync_all_from_sheets()
    return result


@app.get("/solver/run", response_model=WeeklyScheduleResult)
async def run_ep(pass_key: str, start_date: str, end_date: str) -> WeeklyScheduleResult:
    if pass_key != SOLVER_PASS_KEY:
        raise HTTPException(status_code=422, detail="Invalid Credentials")

    # Parse date strings
    try:
        parsed_start = date.fromisoformat(start_date)
        parsed_end = date.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    if parsed_end < parsed_start:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")

    locked_shifts = []
    current_schedule = await ScheduleRunDoc.find_one(ScheduleRunDoc.is_current == True)
    if current_schedule:
        for assignment in current_schedule.assignments:
            if assignment.is_locked and assignment.total_hours > 0 and assignment.date:
                scheduled_periods = [
                    p.period_index for p in assignment.periods if p.scheduled
                ]
                if scheduled_periods:
                    locked_shifts.append({
                        "employee_name": assignment.employee_name,
                        "date": assignment.date,
                        "periods": scheduled_periods,
                    })

    staffing_requirements = await get_staffing_requirements()

    config = await ConfigDoc.find_one()
    solver_type = getattr(config, "solver_type", "gurobi") if config else "gurobi"

    # Fetch store jurisdiction and compliance rules dynamically
    store = await StoreDoc.find_one()
    jurisdiction = store.jurisdiction if store else "DEFAULT"

    # Fetch compliance rules for this jurisdiction (or fall back to DEFAULT)
    compliance_rule = await ComplianceRuleDoc.find_one(
        ComplianceRuleDoc.jurisdiction == jurisdiction
    )
    if not compliance_rule and jurisdiction != "DEFAULT":
        # Fall back to DEFAULT rules if jurisdiction-specific rules not found
        compliance_rule = await ComplianceRuleDoc.find_one(
            ComplianceRuleDoc.jurisdiction == "DEFAULT"
        )

    # Build compliance rules dict for solver
    compliance_rules = {
        "min_rest_hours": compliance_rule.min_rest_hours if compliance_rule else 8.0,
        "minor_curfew_end": compliance_rule.minor_curfew_end if compliance_rule else "22:00",
        "minor_earliest_start": compliance_rule.minor_earliest_start if compliance_rule else "06:00",
        "minor_max_daily_hours": compliance_rule.minor_max_daily_hours if compliance_rule else 8.0,
        "minor_max_weekly_hours": compliance_rule.minor_max_weekly_hours if compliance_rule else 40.0,
        "minor_age_threshold": compliance_rule.minor_age_threshold if compliance_rule else 18,
        "daily_overtime_threshold": compliance_rule.daily_overtime_threshold if compliance_rule else None,
        "weekly_overtime_threshold": compliance_rule.weekly_overtime_threshold if compliance_rule else 40.0,
        "meal_break_after_hours": compliance_rule.meal_break_after_hours if compliance_rule else 5.0,
        "meal_break_duration_minutes": compliance_rule.meal_break_duration_minutes if compliance_rule else 30,
    }

    try:
        result = main(
            start_date=parsed_start,
            end_date=parsed_end,
            locked_shifts=locked_shifts if locked_shifts else None,
            staffing_requirements=staffing_requirements,
            solver_type=solver_type,
            compliance_rules=compliance_rules,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await _persist_schedule_result(result, locked_shifts=locked_shifts if locked_shifts else None)

    # Run post-validation compliance checks
    merged_schedule = await ScheduleRunDoc.find_one(ScheduleRunDoc.is_current == True)

    if merged_schedule:
        await _run_compliance_validation(merged_schedule)

    # Reload to get updated violations
    merged_schedule = await ScheduleRunDoc.find_one(ScheduleRunDoc.is_current == True)
    return _schedule_run_to_result(merged_schedule)


async def _persist_schedule_result(result: WeeklyScheduleResult, locked_shifts: list[dict] | None = None):
    locked_lookup = {}
    if locked_shifts:
        for ls in locked_shifts:
            key = (ls["employee_name"], ls["date"])
            locked_lookup[key] = set(ls["periods"])

    new_assignments = []
    for schedule in result.schedules:
        schedule_key = (schedule.employee_name, schedule.date)
        is_schedule_locked = schedule_key in locked_lookup
        locked_periods = locked_lookup.get(schedule_key, set())

        periods = [
            ShiftPeriodEmbed(
                period_index=p.period_index,
                start_time=p.start_time,
                end_time=p.end_time,
                scheduled=p.scheduled,
                is_locked=p.period_index in locked_periods if p.scheduled else False,
                is_break=p.is_break,
            )
            for p in schedule.periods
        ]
        new_assignments.append(
            Assignment(
                employee_name=schedule.employee_name,
                day_of_week=schedule.day_of_week,
                date=schedule.date,
                total_hours=schedule.total_hours,
                shift_start=schedule.shift_start,
                shift_end=schedule.shift_end,
                is_short_shift=schedule.is_short_shift,
                is_locked=is_schedule_locked,
                periods=periods,
            )
        )

    new_daily_summaries = []
    for summary in result.daily_summaries:
        unfilled = [
            UnfilledPeriodEmbed(
                period_index=u.period_index,
                start_time=u.start_time,
                end_time=u.end_time,
                workers_needed=u.workers_needed,
            )
            for u in summary.unfilled_periods
        ]
        new_daily_summaries.append(
            DailySummary(
                day_of_week=summary.day_of_week,
                date=summary.date,
                total_cost=summary.total_cost,
                employees_scheduled=summary.employees_scheduled,
                total_labor_hours=summary.total_labor_hours,
                dummy_worker_cost=summary.dummy_worker_cost,
                unfilled_periods=unfilled,
            )
        )

    new_start = date.fromisoformat(result.start_date)
    new_end = date.fromisoformat(result.end_date)
    new_dates = set(a.date for a in new_assignments if a.date)

    current_schedule = await ScheduleRunDoc.find_one(ScheduleRunDoc.is_current == True)

    if current_schedule and current_schedule.store_name == result.store_name:
        existing_assignments = [
            a for a in current_schedule.assignments
            if a.date and a.date not in new_dates
        ]
        existing_summaries = [
            s for s in current_schedule.daily_summaries
            if s.date and s.date not in new_dates
        ]

        merged_assignments = existing_assignments + new_assignments
        merged_summaries = existing_summaries + new_daily_summaries

        all_dates = []
        for a in merged_assignments:
            if a.date:
                all_dates.append(date.fromisoformat(a.date))
        if current_schedule.start_date:
            all_dates.append(current_schedule.start_date.date())
        if current_schedule.end_date:
            all_dates.append(current_schedule.end_date.date())
        all_dates.extend([new_start, new_end])

        merged_start = min(all_dates)
        merged_end = max(all_dates)

        total_cost = sum(s.total_cost for s in merged_summaries)
        total_dummy = sum(s.dummy_worker_cost for s in merged_summaries)
        total_short_shift = result.total_short_shift_penalty

        await current_schedule.set({
            "start_date": datetime.combine(merged_start, datetime.min.time()),
            "end_date": datetime.combine(merged_end, datetime.min.time()),
            "generated_at": datetime.fromisoformat(result.generated_at),
            "total_weekly_cost": total_cost,
            "total_dummy_worker_cost": total_dummy,
            "total_short_shift_penalty": total_short_shift,
            "status": result.status,
            "has_warnings": total_dummy > 0 or total_short_shift > 0,
            "is_edited": False,
            "last_edited_at": None,
            "daily_summaries": merged_summaries,
            "assignments": merged_assignments,
        })
    else:
        await ScheduleRunDoc.find(ScheduleRunDoc.is_current == True).update_many(
            {"$set": {"is_current": False}}
        )

        schedule_run = ScheduleRunDoc(
            start_date=datetime.fromisoformat(result.start_date),
            end_date=datetime.fromisoformat(result.end_date),
            store_name=result.store_name,
            generated_at=datetime.fromisoformat(result.generated_at),
            total_weekly_cost=result.total_weekly_cost,
            total_dummy_worker_cost=result.total_dummy_worker_cost,
            total_short_shift_penalty=result.total_short_shift_penalty,
            status=result.status,
            has_warnings=result.has_warnings,
            is_current=True,
            daily_summaries=new_daily_summaries,
            assignments=new_assignments,
        )
        await schedule_run.insert()


async def _run_compliance_validation(schedule_run: ScheduleRunDoc):
    """Run compliance validation and save violations to the schedule."""
    from compliance.engine import validate_schedule_compliance

    # Get employees for validation
    employees = await EmployeeDoc.find(EmployeeDoc.disabled == False).to_list()

    # Get config for compliance mode
    config = await ConfigDoc.find_one()
    if config and config.compliance_mode == "off":
        # Clear any existing violations if compliance is off
        await schedule_run.set({"compliance_violations": [], "has_warnings": schedule_run.has_warnings})
        return

    # Run validation (function fetches rules internally based on store's jurisdiction)
    result = await validate_schedule_compliance(schedule_run, employees)

    # Convert violations to embedded documents
    violations = [
        ComplianceViolation(
            rule_type=v.rule_type.value,
            severity=v.severity.value,
            employee_name=v.employee_name,
            date=v.date,
            message=v.message,
            details=v.details,
        )
        for v in result.violations
    ]

    # Update schedule with violations
    has_warnings = (
        schedule_run.total_dummy_worker_cost > 0 or
        schedule_run.total_short_shift_penalty > 0 or
        len(violations) > 0
    )

    await schedule_run.set({
        "compliance_violations": violations,
        "has_warnings": has_warnings,
    })


@app.get("/schedule/results")
async def get_schedule_results() -> WeeklyScheduleResult | None:
    schedule_run = await ScheduleRunDoc.find_one(ScheduleRunDoc.is_current == True)

    if not schedule_run:
        return None

    return _schedule_run_to_result(schedule_run)


def _schedule_run_to_result(schedule_run: ScheduleRunDoc) -> WeeklyScheduleResult:
    from schemas import EmployeeDaySchedule, DayScheduleSummary, ShiftPeriod, UnfilledPeriod, ComplianceViolationSchema

    schedules = []
    for assignment in schedule_run.assignments:
        periods = [
            ShiftPeriod(
                period_index=p.period_index,
                start_time=p.start_time,
                end_time=p.end_time,
                scheduled=p.scheduled,
                is_locked=getattr(p, 'is_locked', False),
                is_break=getattr(p, 'is_break', False),
            )
            for p in assignment.periods
        ]
        schedules.append(
            EmployeeDaySchedule(
                employee_name=assignment.employee_name,
                day_of_week=assignment.day_of_week,
                date=getattr(assignment, 'date', None),
                periods=periods,
                total_hours=assignment.total_hours,
                shift_start=assignment.shift_start,
                shift_end=assignment.shift_end,
                is_short_shift=assignment.is_short_shift,
                is_locked=getattr(assignment, 'is_locked', False),
            )
        )

    daily_summaries = []
    for summary in schedule_run.daily_summaries:
        unfilled = [
            UnfilledPeriod(
                period_index=u.period_index,
                start_time=u.start_time,
                end_time=u.end_time,
                workers_needed=u.workers_needed,
            )
            for u in summary.unfilled_periods
        ]
        daily_summaries.append(
            DayScheduleSummary(
                day_of_week=summary.day_of_week,
                date=getattr(summary, 'date', None),
                total_cost=summary.total_cost,
                employees_scheduled=summary.employees_scheduled,
                total_labor_hours=summary.total_labor_hours,
                dummy_worker_cost=summary.dummy_worker_cost,
                unfilled_periods=unfilled,
            )
        )

    # Handle backward compatibility for old schedules without dates
    if schedule_run.start_date:
        start_date_str = schedule_run.start_date.strftime("%Y-%m-%d")
    else:
        # Fallback for old data - use generated_at date and derive Monday of that week
        gen_date = schedule_run.generated_at.date()
        days_since_monday = gen_date.weekday()
        monday = gen_date - timedelta(days=days_since_monday)
        start_date_str = monday.strftime("%Y-%m-%d")

    if schedule_run.end_date:
        end_date_str = schedule_run.end_date.strftime("%Y-%m-%d")
    else:
        # Fallback - assume week schedule (Monday to Sunday)
        gen_date = schedule_run.generated_at.date()
        days_since_monday = gen_date.weekday()
        monday = gen_date - timedelta(days=days_since_monday)
        sunday = monday + timedelta(days=6)
        end_date_str = sunday.strftime("%Y-%m-%d")

    # Convert compliance violations
    violations = [
        ComplianceViolationSchema(
            rule_type=v.rule_type,
            severity=v.severity,
            employee_name=v.employee_name,
            date=v.date,
            message=v.message,
            details=v.details,
        )
        for v in (schedule_run.compliance_violations or [])
    ]

    return WeeklyScheduleResult(
        start_date=start_date_str,
        end_date=end_date_str,
        store_name=schedule_run.store_name,
        generated_at=schedule_run.generated_at.isoformat(),
        schedules=schedules,
        daily_summaries=daily_summaries,
        total_weekly_cost=schedule_run.total_weekly_cost,
        status=schedule_run.status,
        total_dummy_worker_cost=schedule_run.total_dummy_worker_cost,
        total_short_shift_penalty=schedule_run.total_short_shift_penalty,
        has_warnings=schedule_run.has_warnings,
        is_edited=schedule_run.is_edited,
        last_edited_at=schedule_run.last_edited_at.isoformat() if schedule_run.last_edited_at else None,
        compliance_violations=violations,
    )


@app.get("/schedule/history")
async def get_schedule_history(limit: int = 20, skip: int = 0):
    runs = (
        await ScheduleRunDoc.find()
        .sort(-ScheduleRunDoc.generated_at)
        .skip(skip)
        .limit(limit)
        .to_list()
    )

    results = []
    for run in runs:
        # Handle backward compatibility for old schedules without dates
        if run.start_date:
            start_date_str = run.start_date.strftime("%Y-%m-%d")
        else:
            gen_date = run.generated_at.date()
            days_since_monday = gen_date.weekday()
            monday = gen_date - timedelta(days=days_since_monday)
            start_date_str = monday.strftime("%Y-%m-%d")

        if run.end_date:
            end_date_str = run.end_date.strftime("%Y-%m-%d")
        else:
            gen_date = run.generated_at.date()
            days_since_monday = gen_date.weekday()
            monday = gen_date - timedelta(days=days_since_monday)
            sunday = monday + timedelta(days=6)
            end_date_str = sunday.strftime("%Y-%m-%d")

        results.append({
            "id": str(run.id),
            "start_date": start_date_str,
            "end_date": end_date_str,
            "store_name": run.store_name,
            "generated_at": run.generated_at.isoformat(),
            "total_weekly_cost": run.total_weekly_cost,
            "status": run.status,
            "has_warnings": run.has_warnings,
            "is_current": run.is_current,
        })

    return results


@app.get("/schedule/{schedule_id}")
async def get_schedule_by_id(schedule_id: str) -> WeeklyScheduleResult:
    from beanie import PydanticObjectId

    try:
        run = await ScheduleRunDoc.get(PydanticObjectId(schedule_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if not run:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return _schedule_run_to_result(run)


@app.get("/logs")
def read_logs():
    log_path = os.path.join(os.path.dirname(__file__), "myapp.log")
    try:
        with open(log_path, "r") as logfile:
            logs = logfile.read()
            return logs
    except FileNotFoundError:
        return "Log file not found"


@app.get("/employees")
async def get_employees():
    from datetime import date as date_type

    employees = await EmployeeDoc.find(EmployeeDoc.disabled == False).to_list()

    if not employees:
        return [e.model_dump() for e in data_import.employee]

    # Get store's jurisdiction to determine minor age threshold
    store = await StoreDoc.find_one()
    jurisdiction = store.jurisdiction if store else "DEFAULT"

    # Get compliance rules for jurisdiction
    compliance_rule = await ComplianceRuleDoc.find_one(
        ComplianceRuleDoc.jurisdiction == jurisdiction
    )
    if not compliance_rule and jurisdiction != "DEFAULT":
        compliance_rule = await ComplianceRuleDoc.find_one(
            ComplianceRuleDoc.jurisdiction == "DEFAULT"
        )

    # Use jurisdiction-specific age threshold (default 18 if not set)
    minor_age_threshold = compliance_rule.minor_age_threshold if compliance_rule else 18

    def calculate_is_minor(emp: EmployeeDoc, age_threshold: int) -> bool:
        """Auto-calculate minor status from DOB using jurisdiction's age threshold."""
        if emp.is_minor:
            return True
        if emp.date_of_birth:
            today = date_type.today()
            age = today.year - emp.date_of_birth.year
            if (today.month, today.day) < (emp.date_of_birth.month, emp.date_of_birth.day):
                age -= 1
            return age < age_threshold
        return False

    return [
        {
            "employee_name": e.employee_name,
            "hourly_rate": e.hourly_rate,
            "minimum_hours_per_week": e.minimum_hours_per_week,
            "minimum_hours": e.minimum_hours,
            "maximum_hours": e.maximum_hours,
            "date_of_birth": e.date_of_birth.isoformat() if e.date_of_birth else None,
            "is_minor": calculate_is_minor(e, minor_age_threshold),
            "availability": [
                {
                    "day_of_week": a.day_of_week,
                    "start_time": normalize_time(a.start_time),
                    "end_time": normalize_time(a.end_time),
                }
                for a in e.availability
            ],
        }
        for e in employees
    ]


class AvailabilitySlotUpdate(BaseModel):
    day_of_week: str
    start_time: str
    end_time: str


class EmployeeAvailabilityUpdate(BaseModel):
    availability: list[AvailabilitySlotUpdate]


@app.put("/employees/{employee_name}/availability")
async def update_employee_availability(employee_name: str, request: EmployeeAvailabilityUpdate):
    from db.models import AvailabilitySlot

    employee = await EmployeeDoc.find_one(EmployeeDoc.employee_name == employee_name)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    availability = [
        AvailabilitySlot(
            day_of_week=a.day_of_week,
            start_time=a.start_time,
            end_time=a.end_time,
        )
        for a in request.availability
    ]

    await employee.set({
        "availability": availability,
        "updated_at": datetime.utcnow(),
    })

    return {"success": True, "employee_name": employee_name}


def normalize_time(time_str: str) -> str:
    """Convert various time formats to HH:MM 24-hour format."""
    if not time_str:
        return time_str

    time_str = time_str.strip()

    # Already in HH:MM format
    if len(time_str) == 5 and time_str[2] == ':':
        return time_str

    # Handle AM/PM formats like "6:30:00 AM" or "7:00 PM"
    time_upper = time_str.upper()
    is_pm = 'PM' in time_upper
    is_am = 'AM' in time_upper

    if is_am or is_pm:
        # Remove AM/PM and extra spaces
        time_part = time_upper.replace('AM', '').replace('PM', '').strip()
        parts = time_part.split(':')
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0

        # Convert to 24-hour format
        if is_pm and hours != 12:
            hours += 12
        elif is_am and hours == 12:
            hours = 0

        return f"{hours:02d}:{minutes:02d}"

    # Try to parse as HH:MM:SS
    parts = time_str.split(':')
    if len(parts) >= 2:
        hours = int(parts[0])
        minutes = int(parts[1])
        return f"{hours:02d}:{minutes:02d}"

    return time_str


@app.get("/stores")
async def get_stores():
    stores = await StoreDoc.find().to_list()

    if not stores:
        return [s.model_dump() for s in data_import.stores]

    result = []
    for store in stores:
        for hours in store.hours:
            result.append(
                {
                    "store_name": store.store_name,
                    "day_of_week": hours.day_of_week,
                    "start_time": normalize_time(hours.start_time),
                    "end_time": normalize_time(hours.end_time),
                }
            )
    return result


@app.get("/schedules")
async def get_schedules():
    employees = await EmployeeDoc.find(EmployeeDoc.disabled == False).to_list()

    if not employees:
        return [s.model_dump() for s in data_import.schedule]

    result = []
    for emp in employees:
        for avail in emp.availability:
            result.append(
                {
                    "employee_name": emp.employee_name,
                    "day_of_week": avail.day_of_week,
                    "availability": f"{avail.start_time} - {avail.end_time}",
                }
            )
    return result


VALID_SOLVER_TYPES = ["gurobi", "pulp", "ortools"]


@app.get("/config")
async def get_config():
    config = await ConfigDoc.find_one()

    if not config:
        data_import.load_data()
        return data_import.config.model_dump()

    return {
        "dummy_worker_cost": config.dummy_worker_cost,
        "short_shift_penalty": config.short_shift_penalty,
        "min_shift_hours": config.min_shift_hours,
        "max_daily_hours": config.max_daily_hours,
        "solver_type": getattr(config, "solver_type", "gurobi"),
    }


@app.post("/config")
async def update_config(
    dummy_worker_cost: float | None = None,
    short_shift_penalty: float | None = None,
    min_shift_hours: float | None = None,
    max_daily_hours: float | None = None,
    solver_type: str | None = None,
):
    config = await ConfigDoc.find_one()

    if not config:
        config = ConfigDoc()

    updates = {}
    if dummy_worker_cost is not None:
        updates["dummy_worker_cost"] = dummy_worker_cost
    if short_shift_penalty is not None:
        updates["short_shift_penalty"] = short_shift_penalty
    if min_shift_hours is not None:
        updates["min_shift_hours"] = min_shift_hours
    if max_daily_hours is not None:
        updates["max_daily_hours"] = max_daily_hours
    if solver_type is not None:
        if solver_type not in VALID_SOLVER_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid solver_type. Must be one of: {VALID_SOLVER_TYPES}"
            )
        updates["solver_type"] = solver_type

    if updates:
        updates["updated_at"] = datetime.utcnow()
        if config.id:
            await config.set(updates)
        else:
            for key, value in updates.items():
                setattr(config, key, value)
            await config.insert()

    config = await ConfigDoc.find_one()
    return {
        "dummy_worker_cost": config.dummy_worker_cost,
        "short_shift_penalty": config.short_shift_penalty,
        "min_shift_hours": config.min_shift_hours,
        "max_daily_hours": config.max_daily_hours,
        "solver_type": getattr(config, "solver_type", "gurobi"),
    }


@app.post("/schedule/{schedule_id}/validate", response_model=ValidateChangeResponse)
async def validate_change(schedule_id: str, request: ValidateChangeRequest):
    from beanie import PydanticObjectId
    from schemas import EmployeeDaySchedule as EDS, ShiftPeriod as SP

    try:
        schedule_run = await ScheduleRunDoc.get(PydanticObjectId(schedule_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if not schedule_run:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Convert assignments to EmployeeDaySchedule for validation
    current_schedules = []
    for assignment in schedule_run.assignments:
        periods = [
            SP(
                period_index=p.period_index,
                start_time=p.start_time,
                end_time=p.end_time,
                scheduled=p.scheduled,
                is_locked=getattr(p, 'is_locked', False),
                is_break=getattr(p, 'is_break', False),
            )
            for p in assignment.periods
        ]
        current_schedules.append(
            EDS(
                employee_name=assignment.employee_name,
                day_of_week=assignment.day_of_week,
                date=assignment.date,
                periods=periods,
                total_hours=assignment.total_hours,
                shift_start=assignment.shift_start,
                shift_end=assignment.shift_end,
                is_short_shift=assignment.is_short_shift,
                is_locked=getattr(assignment, 'is_locked', False),
            )
        )

    is_valid, errors, warnings = await validate_schedule_change(
        employee_name=request.employee_name,
        day_of_week=request.day_of_week,
        proposed_start=request.proposed_start,
        proposed_end=request.proposed_end,
        current_schedules=current_schedules,
    )

    return ValidateChangeResponse(
        is_valid=is_valid,
        errors=[ValidationErrorSchema(code=e.code, message=e.message) for e in errors],
        warnings=[ValidationWarningSchema(code=w.code, message=w.message) for w in warnings],
    )


@app.patch("/schedule/{schedule_id}/assignment", response_model=ShiftUpdateResponse)
async def update_assignment(schedule_id: str, request: ShiftUpdateRequest):
    from beanie import PydanticObjectId
    from schemas import EmployeeDaySchedule as EDS, ShiftPeriod as SP, DayScheduleSummary as DSS, UnfilledPeriod as UP

    try:
        schedule_run = await ScheduleRunDoc.get(PydanticObjectId(schedule_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if not schedule_run:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Convert assignments to EmployeeDaySchedule
    current_schedules = []
    for assignment in schedule_run.assignments:
        periods = [
            SP(
                period_index=p.period_index,
                start_time=p.start_time,
                end_time=p.end_time,
                scheduled=p.scheduled,
                is_locked=getattr(p, 'is_locked', False),
                is_break=getattr(p, 'is_break', False),
            )
            for p in assignment.periods
        ]
        current_schedules.append(
            EDS(
                employee_name=assignment.employee_name,
                day_of_week=assignment.day_of_week,
                date=assignment.date,
                periods=periods,
                total_hours=assignment.total_hours,
                shift_start=assignment.shift_start,
                shift_end=assignment.shift_end,
                is_short_shift=assignment.is_short_shift,
                is_locked=getattr(assignment, 'is_locked', False),
            )
        )

    # Convert daily summaries
    current_summaries = []
    for summary in schedule_run.daily_summaries:
        unfilled = [
            UP(
                period_index=u.period_index,
                start_time=u.start_time,
                end_time=u.end_time,
                workers_needed=u.workers_needed,
            )
            for u in summary.unfilled_periods
        ]
        current_summaries.append(
            DSS(
                day_of_week=summary.day_of_week,
                date=getattr(summary, 'date', None),
                total_cost=summary.total_cost,
                employees_scheduled=summary.employees_scheduled,
                total_labor_hours=summary.total_labor_hours,
                dummy_worker_cost=summary.dummy_worker_cost,
                unfilled_periods=unfilled,
            )
        )

    target_employee = request.new_employee_name or request.employee_name
    is_valid, errors, _ = await validate_schedule_change(
        employee_name=target_employee,
        day_of_week=request.day_of_week,
        proposed_start=request.new_shift_start,
        proposed_end=request.new_shift_end,
        current_schedules=current_schedules,
        skip_availability_check=True,
    )

    if not is_valid:
        error_messages = "; ".join([e.message for e in errors])
        raise HTTPException(status_code=400, detail=f"Invalid schedule change: {error_messages}")

    # Get config for update
    config = await get_solver_config()

    # Find and update the schedule
    updated_schedules = []
    schedule_found = False

    def matches_request(schedule, employee_name, day_of_week, date=None):
        if schedule.employee_name != employee_name:
            return False
        if date and schedule.date:
            return schedule.date == date
        return schedule.day_of_week == day_of_week

    for schedule in current_schedules:
        if matches_request(schedule, request.employee_name, request.day_of_week, request.date):
            schedule_found = True

            if request.new_employee_name and request.new_employee_name != request.employee_name:
                # Reassigning to different employee - clear original
                updated_schedule = update_assignment_times(schedule, "00:00", "00:00", config)
                updated_schedules.append(updated_schedule)

                # Find or create target employee's schedule for that day
                target_found = False
                for target_schedule in current_schedules:
                    if matches_request(target_schedule, request.new_employee_name, request.day_of_week, request.date):
                        target_found = True
                        # Skip here, will update in main loop
                        break

                if not target_found:
                    # Need to create a new schedule entry for target employee
                    # Copy periods from the original schedule but mark none as scheduled
                    new_periods = [
                        SP(
                            period_index=p.period_index,
                            start_time=p.start_time,
                            end_time=p.end_time,
                            scheduled=False,
                        )
                        for p in schedule.periods
                    ]
                    new_schedule = EDS(
                        employee_name=request.new_employee_name,
                        day_of_week=request.day_of_week,
                        date=request.date or schedule.date,
                        periods=new_periods,
                        total_hours=0,
                        shift_start=None,
                        shift_end=None,
                        is_short_shift=False,
                    )
                    new_schedule = update_assignment_times(new_schedule, request.new_shift_start, request.new_shift_end, config)
                    updated_schedules.append(new_schedule)
            else:
                # Same employee, just update times
                updated_schedule = update_assignment_times(schedule, request.new_shift_start, request.new_shift_end, config)
                updated_schedules.append(updated_schedule)
        elif request.new_employee_name and matches_request(schedule, request.new_employee_name, request.day_of_week, request.date):
            # This is the target employee for reassignment
            updated_schedule = update_assignment_times(schedule, request.new_shift_start, request.new_shift_end, config)
            updated_schedules.append(updated_schedule)
        else:
            updated_schedules.append(schedule)

    if not schedule_found:
        raise HTTPException(status_code=404, detail=f"No schedule found for {request.employee_name} on {request.day_of_week}")

    # Recalculate costs
    staffing_reqs = await get_staffing_requirements()
    updated_summaries, total_cost, total_dummy, total_short_shift = await recalculate_schedule_costs(
        updated_schedules, current_summaries, staffing_reqs
    )

    # Update database
    updated_assignments = []
    for schedule in updated_schedules:
        periods = [
            ShiftPeriodEmbed(
                period_index=p.period_index,
                start_time=p.start_time,
                end_time=p.end_time,
                scheduled=p.scheduled,
                is_locked=getattr(p, 'is_locked', False),
                is_break=getattr(p, 'is_break', False),
            )
            for p in schedule.periods
        ]
        updated_assignments.append(
            Assignment(
                employee_name=schedule.employee_name,
                day_of_week=schedule.day_of_week,
                date=schedule.date,
                total_hours=schedule.total_hours,
                shift_start=schedule.shift_start,
                shift_end=schedule.shift_end,
                is_short_shift=schedule.is_short_shift,
                is_locked=getattr(schedule, 'is_locked', False),
                periods=periods,
            )
        )

    updated_daily_summaries = []
    for summary in updated_summaries:
        unfilled = [
            UnfilledPeriodEmbed(
                period_index=u.period_index,
                start_time=u.start_time,
                end_time=u.end_time,
                workers_needed=u.workers_needed,
            )
            for u in summary.unfilled_periods
        ]
        updated_daily_summaries.append(
            DailySummary(
                day_of_week=summary.day_of_week,
                date=summary.date,
                total_cost=summary.total_cost,
                employees_scheduled=summary.employees_scheduled,
                total_labor_hours=summary.total_labor_hours,
                dummy_worker_cost=summary.dummy_worker_cost,
                unfilled_periods=unfilled,
            )
        )

    # Save to database
    has_warnings = total_dummy > 0 or total_short_shift > 0
    await schedule_run.set({
        "assignments": updated_assignments,
        "daily_summaries": updated_daily_summaries,
        "total_weekly_cost": total_cost,
        "total_dummy_worker_cost": total_dummy,
        "total_short_shift_penalty": total_short_shift,
        "has_warnings": has_warnings,
        "is_edited": True,
        "last_edited_at": datetime.utcnow(),
    })

    # Return updated result
    updated_run = await ScheduleRunDoc.get(PydanticObjectId(schedule_id))
    result = _schedule_run_to_result(updated_run)

    return ShiftUpdateResponse(
        success=True,
        updated_schedule=result,
        recalculated_cost=total_cost,
    )


@app.post("/schedule/{schedule_id}/batch-update", response_model=BatchUpdateResponse)
async def batch_update_assignments(schedule_id: str, request: BatchUpdateRequest):
    from beanie import PydanticObjectId

    try:
        schedule_run = await ScheduleRunDoc.get(PydanticObjectId(schedule_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if not schedule_run:
        raise HTTPException(status_code=404, detail="Schedule not found")

    failed_updates = []
    current_result = None

    # Apply each update sequentially
    for update in request.updates:
        try:
            result = await update_assignment(schedule_id, update)
            current_result = result
        except HTTPException as e:
            failed_updates.append({
                "employee_name": update.employee_name,
                "day_of_week": update.day_of_week,
                "error": e.detail,
            })

    if current_result is None:
        # All updates failed, return current state
        result = _schedule_run_to_result(schedule_run)
        return BatchUpdateResponse(
            success=False,
            updated_schedule=result,
            recalculated_cost=schedule_run.total_weekly_cost,
            failed_updates=failed_updates,
        )

    return BatchUpdateResponse(
        success=len(failed_updates) == 0,
        updated_schedule=current_result.updated_schedule,
        recalculated_cost=current_result.recalculated_cost,
        failed_updates=failed_updates,
    )


@app.patch("/schedule/{schedule_id}/lock", response_model=ToggleLockResponse)
async def toggle_shift_lock(schedule_id: str, request: ToggleLockRequest):
    from beanie import PydanticObjectId

    try:
        schedule_run = await ScheduleRunDoc.get(PydanticObjectId(schedule_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if not schedule_run:
        raise HTTPException(status_code=404, detail="Schedule not found")

    assignment_found = False
    for assignment in schedule_run.assignments:
        if assignment.employee_name == request.employee_name and assignment.date == request.date:
            assignment.is_locked = request.is_locked
            # Also update periods' is_locked status for scheduled periods
            for period in assignment.periods:
                if period.scheduled:
                    period.is_locked = request.is_locked
            assignment_found = True
            break

    if not assignment_found:
        raise HTTPException(
            status_code=404,
            detail=f"No assignment found for {request.employee_name} on {request.date}"
        )

    # Save to database
    await schedule_run.set({
        "assignments": schedule_run.assignments,
        "last_edited_at": datetime.utcnow(),
    })

    # Return updated result
    updated_run = await ScheduleRunDoc.get(PydanticObjectId(schedule_id))
    result = _schedule_run_to_result(updated_run)

    return ToggleLockResponse(
        success=True,
        updated_schedule=result,
    )


class DeleteShiftRequest(BaseModel):
    employee_name: str
    day_of_week: str


class DeleteShiftResponse(BaseModel):
    success: bool
    updated_schedule: WeeklyScheduleResult


class StoreHoursUpdate(BaseModel):
    day_of_week: str
    start_time: str
    end_time: str


class StoreUpdateRequest(BaseModel):
    store_name: str | None = None
    hours: list[StoreHoursUpdate]


class CreateStoreRequest(BaseModel):
    store_name: str
    hours: list[StoreHoursUpdate] = []


@app.delete("/schedule/{schedule_id}/shift", response_model=DeleteShiftResponse)
async def delete_shift(schedule_id: str, request: DeleteShiftRequest):
    from beanie import PydanticObjectId

    try:
        schedule_run = await ScheduleRunDoc.get(PydanticObjectId(schedule_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if not schedule_run:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Find and clear the assignment
    assignment_found = False
    for assignment in schedule_run.assignments:
        if assignment.employee_name == request.employee_name and assignment.day_of_week == request.day_of_week:
            if assignment.is_locked:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot delete a locked shift. Unlock it first."
                )
            # Clear the shift by setting all periods to not scheduled
            for period in assignment.periods:
                period.scheduled = False
                period.is_locked = False
            assignment.total_hours = 0
            assignment.shift_start = None
            assignment.shift_end = None
            assignment.is_short_shift = False
            assignment.is_locked = False
            assignment_found = True
            break

    if not assignment_found:
        raise HTTPException(
            status_code=404,
            detail=f"No assignment found for {request.employee_name} on {request.day_of_week}"
        )

    # Recalculate daily summary
    from cost_calculator import recalculate_schedule_costs
    from schemas import EmployeeDaySchedule as EDS, ShiftPeriod as SP, DayScheduleSummary as DSS, UnfilledPeriod as UP

    # Convert to schemas for recalculation
    current_schedules = []
    for a in schedule_run.assignments:
        periods = [
            SP(
                period_index=p.period_index,
                start_time=p.start_time,
                end_time=p.end_time,
                scheduled=p.scheduled,
                is_locked=getattr(p, 'is_locked', False),
                is_break=getattr(p, 'is_break', False),
            )
            for p in a.periods
        ]
        current_schedules.append(
            EDS(
                employee_name=a.employee_name,
                day_of_week=a.day_of_week,
                date=getattr(a, 'date', None),
                periods=periods,
                total_hours=a.total_hours,
                shift_start=a.shift_start,
                shift_end=a.shift_end,
                is_short_shift=a.is_short_shift,
                is_locked=getattr(a, 'is_locked', False),
            )
        )

    current_summaries = []
    for summary in schedule_run.daily_summaries:
        unfilled = [
            UP(
                period_index=u.period_index,
                start_time=u.start_time,
                end_time=u.end_time,
                workers_needed=u.workers_needed,
            )
            for u in summary.unfilled_periods
        ]
        current_summaries.append(
            DSS(
                day_of_week=summary.day_of_week,
                total_cost=summary.total_cost,
                employees_scheduled=summary.employees_scheduled,
                total_labor_hours=summary.total_labor_hours,
                dummy_worker_cost=summary.dummy_worker_cost,
                unfilled_periods=unfilled,
            )
        )

    staffing_reqs = await get_staffing_requirements()
    updated_summaries, total_cost, total_dummy, total_short_shift = await recalculate_schedule_costs(
        current_schedules, current_summaries, staffing_reqs
    )

    # Update database
    updated_daily_summaries = []
    for summary in updated_summaries:
        unfilled = [
            UnfilledPeriodEmbed(
                period_index=u.period_index,
                start_time=u.start_time,
                end_time=u.end_time,
                workers_needed=u.workers_needed,
            )
            for u in summary.unfilled_periods
        ]
        updated_daily_summaries.append(
            DailySummary(
                day_of_week=summary.day_of_week,
                date=summary.date,
                total_cost=summary.total_cost,
                employees_scheduled=summary.employees_scheduled,
                total_labor_hours=summary.total_labor_hours,
                dummy_worker_cost=summary.dummy_worker_cost,
                unfilled_periods=unfilled,
            )
        )

    has_warnings = total_dummy > 0 or total_short_shift > 0
    await schedule_run.set({
        "assignments": schedule_run.assignments,
        "daily_summaries": updated_daily_summaries,
        "total_weekly_cost": total_cost,
        "total_dummy_worker_cost": total_dummy,
        "total_short_shift_penalty": total_short_shift,
        "has_warnings": has_warnings,
        "is_edited": True,
        "last_edited_at": datetime.utcnow(),
    })

    # Return updated result
    updated_run = await ScheduleRunDoc.get(PydanticObjectId(schedule_id))
    result = _schedule_run_to_result(updated_run)

    return DeleteShiftResponse(
        success=True,
        updated_schedule=result,
    )


@app.put("/stores/{store_name}")
async def update_store(store_name: str, request: StoreUpdateRequest):
    store = await StoreDoc.find_one(StoreDoc.store_name == store_name)

    hours = [
        StoreHours(
            day_of_week=h.day_of_week,
            start_time=h.start_time,
            end_time=h.end_time,
        )
        for h in request.hours
    ]

    if not store:
        # Store doesn't exist in MongoDB yet (might be from Google Sheets fallback)
        # Create it now
        new_name = request.store_name if request.store_name else store_name
        store = StoreDoc(store_name=new_name, hours=hours)
        await store.insert()
        return {"success": True, "store_name": new_name}

    # Update existing store
    updates = {"updated_at": datetime.utcnow(), "hours": hours}
    if request.store_name and request.store_name != store_name:
        existing = await StoreDoc.find_one(StoreDoc.store_name == request.store_name)
        if existing:
            raise HTTPException(status_code=400, detail="A store with that name already exists")
        updates["store_name"] = request.store_name

    await store.set(updates)
    return {"success": True, "store_name": updates.get("store_name", store_name)}


@app.post("/stores")
async def create_store(request: CreateStoreRequest):
    existing = await StoreDoc.find_one(StoreDoc.store_name == request.store_name)
    if existing:
        raise HTTPException(status_code=400, detail="Store already exists")

    store = StoreDoc(
        store_name=request.store_name,
        hours=[
            StoreHours(
                day_of_week=h.day_of_week,
                start_time=h.start_time,
                end_time=h.end_time,
            )
            for h in request.hours
        ],
    )
    await store.insert()
    return {"success": True, "store_name": request.store_name}


@app.delete("/stores/{store_name}")
async def delete_store(store_name: str):
    store = await StoreDoc.find_one(StoreDoc.store_name == store_name)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    await store.delete()
    return {"success": True}


class StaffingRequirementUpdate(BaseModel):
    day_type: str
    start_time: str
    end_time: str
    min_staff: int


class StaffingRequirementsUpdate(BaseModel):
    requirements: list[StaffingRequirementUpdate]


@app.get("/stores/{store_name}/staffing")
async def get_store_staffing(store_name: str):
    store = await StoreDoc.find_one(StoreDoc.store_name == store_name)
    if not store:
        return []
    return [
        {
            "day_type": r.day_type,
            "start_time": normalize_time(r.start_time),
            "end_time": normalize_time(r.end_time),
            "min_staff": r.min_staff,
        }
        for r in store.staffing_requirements
    ]


@app.put("/stores/{store_name}/staffing")
async def update_store_staffing(store_name: str, request: StaffingRequirementsUpdate):
    from db.models import StaffingRequirement

    store = await StoreDoc.find_one(StoreDoc.store_name == store_name)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    requirements = [
        StaffingRequirement(
            day_type=r.day_type,
            start_time=r.start_time,
            end_time=r.end_time,
            min_staff=r.min_staff,
        )
        for r in request.requirements
    ]

    await store.set({"staffing_requirements": requirements, "updated_at": datetime.utcnow()})
    return {"success": True, "store_name": store_name}


# ============================================================================
# Compliance Endpoints
# ============================================================================

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}


@app.get("/compliance/states")
async def get_us_states():
    """Get list of US states for compliance rule selection."""
    return [{"code": code, "name": name} for code, name in sorted(US_STATES.items(), key=lambda x: x[1])]


@app.get("/compliance/rules")
async def get_compliance_rules():
    """Get all compliance rules."""
    rules = await ComplianceRuleDoc.find().to_list()
    return [
        {
            "jurisdiction": r.jurisdiction,
            "min_rest_hours": r.min_rest_hours,
            "minor_max_daily_hours": r.minor_max_daily_hours,
            "minor_max_weekly_hours": r.minor_max_weekly_hours,
            "minor_curfew_end": r.minor_curfew_end,
            "minor_earliest_start": r.minor_earliest_start,
            "minor_age_threshold": r.minor_age_threshold,
            "daily_overtime_threshold": r.daily_overtime_threshold,
            "weekly_overtime_threshold": r.weekly_overtime_threshold,
            "meal_break_after_hours": r.meal_break_after_hours,
            "meal_break_duration_minutes": r.meal_break_duration_minutes,
            "rest_break_interval_hours": r.rest_break_interval_hours,
            "rest_break_duration_minutes": r.rest_break_duration_minutes,
            "advance_notice_days": r.advance_notice_days,
            "source": r.source,
            "ai_sources": r.ai_sources,
            "notes": r.notes,
        }
        for r in rules
    ]


@app.get("/compliance/rules/{jurisdiction}")
async def get_compliance_rule(jurisdiction: str):
    """Get compliance rules for a specific jurisdiction."""
    rule = await ComplianceRuleDoc.find_one(ComplianceRuleDoc.jurisdiction == jurisdiction.upper())
    if not rule:
        raise HTTPException(status_code=404, detail=f"No rules found for jurisdiction: {jurisdiction}")
    return {
        "jurisdiction": rule.jurisdiction,
        "min_rest_hours": rule.min_rest_hours,
        "minor_max_daily_hours": rule.minor_max_daily_hours,
        "minor_max_weekly_hours": rule.minor_max_weekly_hours,
        "minor_curfew_end": rule.minor_curfew_end,
        "minor_earliest_start": rule.minor_earliest_start,
        "minor_age_threshold": rule.minor_age_threshold,
        "daily_overtime_threshold": rule.daily_overtime_threshold,
        "weekly_overtime_threshold": rule.weekly_overtime_threshold,
        "meal_break_after_hours": rule.meal_break_after_hours,
        "meal_break_duration_minutes": rule.meal_break_duration_minutes,
        "rest_break_interval_hours": rule.rest_break_interval_hours,
        "rest_break_duration_minutes": rule.rest_break_duration_minutes,
        "advance_notice_days": rule.advance_notice_days,
        "source": rule.source,
        "ai_sources": rule.ai_sources,
        "notes": rule.notes,
    }


class ComplianceRuleUpdate(BaseModel):
    min_rest_hours: float = 8.0
    minor_max_daily_hours: float = 8.0
    minor_max_weekly_hours: float = 40.0
    minor_curfew_end: str = "22:00"
    minor_earliest_start: str = "06:00"
    minor_age_threshold: int = 18
    daily_overtime_threshold: float | None = None
    weekly_overtime_threshold: float = 40.0
    meal_break_after_hours: float = 5.0
    meal_break_duration_minutes: int = 30
    rest_break_interval_hours: float = 4.0
    rest_break_duration_minutes: int = 10
    advance_notice_days: int = 14
    source: str | None = None
    ai_sources: list[str] = []
    notes: str | None = None


@app.post("/compliance/rules/{jurisdiction}")
async def create_or_update_compliance_rule(jurisdiction: str, request: ComplianceRuleUpdate):
    """Create or update compliance rules for a jurisdiction."""
    jurisdiction = jurisdiction.upper()

    rule = await ComplianceRuleDoc.find_one(ComplianceRuleDoc.jurisdiction == jurisdiction)

    if rule:
        await rule.set({
            "min_rest_hours": request.min_rest_hours,
            "minor_max_daily_hours": request.minor_max_daily_hours,
            "minor_max_weekly_hours": request.minor_max_weekly_hours,
            "minor_curfew_end": request.minor_curfew_end,
            "minor_earliest_start": request.minor_earliest_start,
            "minor_age_threshold": request.minor_age_threshold,
            "daily_overtime_threshold": request.daily_overtime_threshold,
            "weekly_overtime_threshold": request.weekly_overtime_threshold,
            "meal_break_after_hours": request.meal_break_after_hours,
            "meal_break_duration_minutes": request.meal_break_duration_minutes,
            "rest_break_interval_hours": request.rest_break_interval_hours,
            "rest_break_duration_minutes": request.rest_break_duration_minutes,
            "advance_notice_days": request.advance_notice_days,
            "source": request.source,
            "ai_sources": request.ai_sources,
            "notes": request.notes,
            "updated_at": datetime.utcnow(),
        })
    else:
        rule = ComplianceRuleDoc(
            jurisdiction=jurisdiction,
            min_rest_hours=request.min_rest_hours,
            minor_max_daily_hours=request.minor_max_daily_hours,
            minor_max_weekly_hours=request.minor_max_weekly_hours,
            minor_curfew_end=request.minor_curfew_end,
            minor_earliest_start=request.minor_earliest_start,
            minor_age_threshold=request.minor_age_threshold,
            daily_overtime_threshold=request.daily_overtime_threshold,
            weekly_overtime_threshold=request.weekly_overtime_threshold,
            meal_break_after_hours=request.meal_break_after_hours,
            meal_break_duration_minutes=request.meal_break_duration_minutes,
            rest_break_interval_hours=request.rest_break_interval_hours,
            rest_break_duration_minutes=request.rest_break_duration_minutes,
            advance_notice_days=request.advance_notice_days,
            source=request.source,
            ai_sources=request.ai_sources,
            notes=request.notes,
        )
        await rule.insert()

    return {"success": True, "jurisdiction": jurisdiction}


@app.delete("/compliance/rules/{jurisdiction}")
async def delete_compliance_rule(jurisdiction: str):
    """Delete compliance rules for a jurisdiction."""
    rule = await ComplianceRuleDoc.find_one(ComplianceRuleDoc.jurisdiction == jurisdiction.upper())
    if not rule:
        raise HTTPException(status_code=404, detail=f"No rules found for jurisdiction: {jurisdiction}")
    await rule.delete()
    return {"success": True}


@app.post("/compliance/ai/research/{state}")
async def research_state_compliance(state: str):
    """Use AI to research labor laws for a state. Returns suggestions for review."""
    state = state.upper()
    if state not in US_STATES and state != "DEFAULT":
        raise HTTPException(status_code=400, detail=f"Invalid state code: {state}")

    try:
        from compliance.ai_assistant import ComplianceAIAssistant, get_default_rules, LITELLM_AVAILABLE

        if not LITELLM_AVAILABLE:
            # Return default rules if LiteLLM is not available
            result = get_default_rules(state)
            result.notes = "LiteLLM not available. Using federal default rules."
            return result.model_dump()

        assistant = ComplianceAIAssistant()
        suggestion = await assistant.research_state_laws(state)
        return suggestion.model_dump()
    except ImportError:
        # Fallback to default rules
        from compliance.ai_assistant import get_default_rules
        result = get_default_rules(state)
        result.notes = "AI module not available. Using federal default rules."
        return result.model_dump()
    except Exception as e:
        # Log the error but return default rules instead of failing
        import logging
        logging.error(f"AI research failed for {state}: {e}")

        from compliance.ai_assistant import get_default_rules
        result = get_default_rules(state)
        result.notes = f"AI research failed ({str(e)[:100]}). Using federal default rules. You can manually edit these values."
        return result.model_dump()


class OriginalAISuggestion(BaseModel):
    """Original AI suggestion values for audit trail comparison."""
    min_rest_hours: float | None = None
    minor_curfew_end: str | None = None
    minor_earliest_start: str | None = None
    minor_max_daily_hours: float | None = None
    minor_max_weekly_hours: float | None = None
    minor_age_threshold: int = 18
    daily_overtime_threshold: float | None = None
    weekly_overtime_threshold: float | None = None
    meal_break_after_hours: float | None = None
    meal_break_duration_minutes: int | None = None
    rest_break_interval_hours: float | None = None
    rest_break_duration_minutes: int | None = None
    advance_notice_days: int | None = None
    sources: list[str] = []
    notes: str | None = None
    model_used: str = ""
    confidence_level: str = ""
    validation_warnings: list[str] = []
    disclaimer: str = ""


class ApproveAISuggestionRequest(BaseModel):
    suggestion_id: str
    jurisdiction: str
    # Approved (potentially edited) values
    min_rest_hours: float | None = None
    minor_curfew_end: str | None = None
    minor_earliest_start: str | None = None
    minor_max_daily_hours: float | None = None
    minor_max_weekly_hours: float | None = None
    minor_age_threshold: int = 18
    daily_overtime_threshold: float | None = None
    weekly_overtime_threshold: float | None = None
    meal_break_after_hours: float | None = None
    meal_break_duration_minutes: int | None = None
    rest_break_interval_hours: float | None = None
    rest_break_duration_minutes: int | None = None
    advance_notice_days: int | None = None
    sources: list[str] = []
    notes: str | None = None
    # Original AI suggestion for audit trail
    original_suggestion: OriginalAISuggestion | None = None


@app.post("/compliance/ai/approve")
async def approve_ai_suggestion(request: ApproveAISuggestionRequest, req: Request):
    """Manager approves AI suggestion, saving it as active rules with audit trail."""
    from db.models import ComplianceAuditDoc, ComplianceRuleEdit

    jurisdiction = request.jurisdiction.upper()

    # Build approved values dict
    approved_values = {
        "min_rest_hours": request.min_rest_hours or 8.0,
        "minor_max_daily_hours": request.minor_max_daily_hours or 8.0,
        "minor_max_weekly_hours": request.minor_max_weekly_hours or 40.0,
        "minor_curfew_end": request.minor_curfew_end or "22:00",
        "minor_earliest_start": request.minor_earliest_start or "06:00",
        "minor_age_threshold": request.minor_age_threshold,
        "daily_overtime_threshold": request.daily_overtime_threshold,
        "weekly_overtime_threshold": request.weekly_overtime_threshold or 40.0,
        "meal_break_after_hours": request.meal_break_after_hours or 5.0,
        "meal_break_duration_minutes": request.meal_break_duration_minutes or 30,
        "rest_break_interval_hours": request.rest_break_interval_hours or 4.0,
        "rest_break_duration_minutes": request.rest_break_duration_minutes or 10,
        "advance_notice_days": request.advance_notice_days or 14,
    }

    # Create audit trail
    human_edits = []
    ai_original = {}

    if request.original_suggestion:
        orig = request.original_suggestion
        ai_original = {
            "min_rest_hours": orig.min_rest_hours,
            "minor_curfew_end": orig.minor_curfew_end,
            "minor_earliest_start": orig.minor_earliest_start,
            "minor_max_daily_hours": orig.minor_max_daily_hours,
            "minor_max_weekly_hours": orig.minor_max_weekly_hours,
            "minor_age_threshold": orig.minor_age_threshold,
            "daily_overtime_threshold": orig.daily_overtime_threshold,
            "weekly_overtime_threshold": orig.weekly_overtime_threshold,
            "meal_break_after_hours": orig.meal_break_after_hours,
            "meal_break_duration_minutes": orig.meal_break_duration_minutes,
            "rest_break_interval_hours": orig.rest_break_interval_hours,
            "rest_break_duration_minutes": orig.rest_break_duration_minutes,
            "advance_notice_days": orig.advance_notice_days,
            "sources": orig.sources,
            "notes": orig.notes,
        }

        # Detect edits by comparing original vs approved
        fields_to_compare = [
            ("min_rest_hours", orig.min_rest_hours, request.min_rest_hours),
            ("minor_curfew_end", orig.minor_curfew_end, request.minor_curfew_end),
            ("minor_earliest_start", orig.minor_earliest_start, request.minor_earliest_start),
            ("minor_max_daily_hours", orig.minor_max_daily_hours, request.minor_max_daily_hours),
            ("minor_max_weekly_hours", orig.minor_max_weekly_hours, request.minor_max_weekly_hours),
            ("minor_age_threshold", orig.minor_age_threshold, request.minor_age_threshold),
            ("daily_overtime_threshold", orig.daily_overtime_threshold, request.daily_overtime_threshold),
            ("weekly_overtime_threshold", orig.weekly_overtime_threshold, request.weekly_overtime_threshold),
            ("meal_break_after_hours", orig.meal_break_after_hours, request.meal_break_after_hours),
            ("meal_break_duration_minutes", orig.meal_break_duration_minutes, request.meal_break_duration_minutes),
            ("rest_break_interval_hours", orig.rest_break_interval_hours, request.rest_break_interval_hours),
            ("rest_break_duration_minutes", orig.rest_break_duration_minutes, request.rest_break_duration_minutes),
            ("advance_notice_days", orig.advance_notice_days, request.advance_notice_days),
        ]

        for field_name, original_val, approved_val in fields_to_compare:
            if original_val != approved_val:
                human_edits.append(ComplianceRuleEdit(
                    field_name=field_name,
                    original_value=str(original_val) if original_val is not None else None,
                    edited_value=str(approved_val) if approved_val is not None else None,
                ))

        # Create audit record
        audit = ComplianceAuditDoc(
            jurisdiction=jurisdiction,
            suggestion_id=request.suggestion_id,
            ai_original=ai_original,
            ai_model_used=orig.model_used,
            ai_confidence_level=orig.confidence_level,
            ai_sources=orig.sources,
            ai_validation_warnings=orig.validation_warnings,
            ai_disclaimer=orig.disclaimer,
            human_edits=human_edits,
            edit_count=len(human_edits),
            approved_values=approved_values,
            ip_address=req.client.host if req.client else None,
            user_agent=req.headers.get("user-agent"),
        )
        await audit.insert()

    # Create or update the compliance rule
    rule = await ComplianceRuleDoc.find_one(ComplianceRuleDoc.jurisdiction == jurisdiction)

    rule_data = {
        **approved_values,
        "source": "AI_SUGGESTED" if request.original_suggestion else "MANUAL",
        "ai_sources": request.sources,
        "notes": request.notes,
        "updated_at": datetime.utcnow(),
    }

    if rule:
        await rule.set(rule_data)
    else:
        rule = ComplianceRuleDoc(jurisdiction=jurisdiction, **rule_data)
        await rule.insert()

    return {
        "success": True,
        "jurisdiction": jurisdiction,
        "edits_made": len(human_edits),
        "audit_created": request.original_suggestion is not None,
    }


@app.get("/compliance/audit")
async def get_compliance_audit_history(
    jurisdiction: str | None = None,
    limit: int = 50,
    skip: int = 0,
):
    """Get compliance rule audit trail for accountability and legal protection."""
    from db.models import ComplianceAuditDoc

    query = {}
    if jurisdiction:
        query["jurisdiction"] = jurisdiction.upper()

    audits = await ComplianceAuditDoc.find(query).sort(
        [("approved_at", -1)]
    ).skip(skip).limit(limit).to_list()

    return [
        {
            "id": str(audit.id),
            "jurisdiction": audit.jurisdiction,
            "suggestion_id": audit.suggestion_id,
            "ai_model_used": audit.ai_model_used,
            "ai_confidence_level": audit.ai_confidence_level,
            "ai_sources": audit.ai_sources,
            "ai_validation_warnings": audit.ai_validation_warnings,
            "ai_original": audit.ai_original,
            "human_edits": [
                {
                    "field_name": e.field_name,
                    "original_value": e.original_value,
                    "edited_value": e.edited_value,
                }
                for e in audit.human_edits
            ],
            "edit_count": audit.edit_count,
            "approved_values": audit.approved_values,
            "approved_at": audit.approved_at.isoformat(),
            "ip_address": audit.ip_address,
        }
        for audit in audits
    ]


@app.get("/compliance/audit/{audit_id}")
async def get_compliance_audit_detail(audit_id: str):
    """Get detailed audit record by ID."""
    from db.models import ComplianceAuditDoc
    from beanie import PydanticObjectId

    try:
        audit = await ComplianceAuditDoc.get(PydanticObjectId(audit_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Audit record not found")

    if not audit:
        raise HTTPException(status_code=404, detail="Audit record not found")

    return {
        "id": str(audit.id),
        "jurisdiction": audit.jurisdiction,
        "suggestion_id": audit.suggestion_id,
        "ai_model_used": audit.ai_model_used,
        "ai_confidence_level": audit.ai_confidence_level,
        "ai_sources": audit.ai_sources,
        "ai_validation_warnings": audit.ai_validation_warnings,
        "ai_disclaimer": audit.ai_disclaimer,
        "ai_original": audit.ai_original,
        "human_edits": [
            {
                "field_name": e.field_name,
                "original_value": e.original_value,
                "edited_value": e.edited_value,
            }
            for e in audit.human_edits
        ],
        "edit_count": audit.edit_count,
        "approved_values": audit.approved_values,
        "approved_at": audit.approved_at.isoformat(),
        "approved_by": audit.approved_by,
        "approval_notes": audit.approval_notes,
        "ip_address": audit.ip_address,
        "user_agent": audit.user_agent,
    }


@app.post("/compliance/validate/{schedule_id}")
async def validate_schedule_compliance_endpoint(schedule_id: str):
    """Validate a schedule for compliance violations."""
    from beanie import PydanticObjectId

    try:
        schedule_run = await ScheduleRunDoc.get(PydanticObjectId(schedule_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if not schedule_run:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Get employees
    employees = await EmployeeDoc.find(EmployeeDoc.disabled == False).to_list()

    # Run compliance validation
    from compliance.engine import validate_schedule_compliance
    result = await validate_schedule_compliance(schedule_run, employees)

    return result.to_dict()


class EmployeeComplianceUpdate(BaseModel):
    date_of_birth: str | None = None  # ISO date string
    is_minor: bool | None = None


@app.patch("/employees/{employee_name}/compliance")
async def update_employee_compliance(employee_name: str, request: EmployeeComplianceUpdate):
    """Update compliance-related fields for an employee."""
    employee = await EmployeeDoc.find_one(EmployeeDoc.employee_name == employee_name)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    updates = {"updated_at": datetime.utcnow()}

    if request.date_of_birth is not None:
        if request.date_of_birth:
            updates["date_of_birth"] = date.fromisoformat(request.date_of_birth)
        else:
            updates["date_of_birth"] = None

    if request.is_minor is not None:
        updates["is_minor"] = request.is_minor

    await employee.set(updates)
    return {"success": True, "employee_name": employee_name}


class ComplianceConfigUpdate(BaseModel):
    compliance_mode: str | None = None  # "off", "warn", "enforce"
    enable_rest_between_shifts: bool | None = None
    enable_minor_restrictions: bool | None = None
    enable_overtime_tracking: bool | None = None
    enable_break_compliance: bool | None = None
    enable_predictive_scheduling: bool | None = None


@app.get("/compliance/config")
async def get_compliance_config():
    """Get compliance configuration."""
    config = await ConfigDoc.find_one()
    if not config:
        return {
            "compliance_mode": "warn",
            "enable_rest_between_shifts": True,
            "enable_minor_restrictions": True,
            "enable_overtime_tracking": True,
            "enable_break_compliance": True,
            "enable_predictive_scheduling": True,
        }
    return {
        "compliance_mode": getattr(config, "compliance_mode", "warn"),
        "enable_rest_between_shifts": getattr(config, "enable_rest_between_shifts", True),
        "enable_minor_restrictions": getattr(config, "enable_minor_restrictions", True),
        "enable_overtime_tracking": getattr(config, "enable_overtime_tracking", True),
        "enable_break_compliance": getattr(config, "enable_break_compliance", True),
        "enable_predictive_scheduling": getattr(config, "enable_predictive_scheduling", True),
    }


@app.post("/compliance/config")
async def update_compliance_config(request: ComplianceConfigUpdate):
    """Update compliance configuration."""
    config = await ConfigDoc.find_one()

    if not config:
        config = ConfigDoc()

    updates = {"updated_at": datetime.utcnow()}

    if request.compliance_mode is not None:
        if request.compliance_mode not in ["off", "warn", "enforce"]:
            raise HTTPException(status_code=400, detail="Invalid compliance_mode")
        updates["compliance_mode"] = request.compliance_mode

    if request.enable_rest_between_shifts is not None:
        updates["enable_rest_between_shifts"] = request.enable_rest_between_shifts
    if request.enable_minor_restrictions is not None:
        updates["enable_minor_restrictions"] = request.enable_minor_restrictions
    if request.enable_overtime_tracking is not None:
        updates["enable_overtime_tracking"] = request.enable_overtime_tracking
    if request.enable_break_compliance is not None:
        updates["enable_break_compliance"] = request.enable_break_compliance
    if request.enable_predictive_scheduling is not None:
        updates["enable_predictive_scheduling"] = request.enable_predictive_scheduling

    if config.id:
        await config.set(updates)
    else:
        for key, value in updates.items():
            setattr(config, key, value)
        await config.insert()

    return await get_compliance_config()


@app.put("/stores/{store_name}/jurisdiction")
async def update_store_jurisdiction(store_name: str, jurisdiction: str):
    """Update the jurisdiction for a store."""
    store = await StoreDoc.find_one(StoreDoc.store_name == store_name)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    jurisdiction = jurisdiction.upper()
    if jurisdiction != "DEFAULT" and jurisdiction not in US_STATES:
        raise HTTPException(status_code=400, detail=f"Invalid jurisdiction: {jurisdiction}")

    await store.set({"jurisdiction": jurisdiction, "updated_at": datetime.utcnow()})
    return {"success": True, "store_name": store_name, "jurisdiction": jurisdiction}
