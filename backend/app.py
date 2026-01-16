import os
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException
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
async def run_ep(pass_key: str) -> WeeklyScheduleResult:
    if pass_key != SOLVER_PASS_KEY:
        raise HTTPException(status_code=422, detail="Invalid Credentials")

    locked_shifts = []
    current_schedule = await ScheduleRunDoc.find_one(ScheduleRunDoc.is_current == True)
    if current_schedule:
        for assignment in current_schedule.assignments:
            if assignment.is_locked and assignment.total_hours > 0:
                scheduled_periods = [
                    p.period_index for p in assignment.periods if p.scheduled
                ]
                if scheduled_periods:
                    locked_shifts.append({
                        "employee_name": assignment.employee_name,
                        "day_of_week": assignment.day_of_week,
                        "periods": scheduled_periods,
                    })

    staffing_requirements = await get_staffing_requirements()

    try:
        result = main(
            locked_shifts=locked_shifts if locked_shifts else None,
            staffing_requirements=staffing_requirements
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await _persist_schedule_result(result, locked_shifts=locked_shifts if locked_shifts else None)

    if locked_shifts:
        locked_lookup = {}
        for ls in locked_shifts:
            key = (ls["employee_name"], ls["day_of_week"])
            locked_lookup[key] = set(ls["periods"])

        for schedule in result.schedules:
            schedule_key = (schedule.employee_name, schedule.day_of_week)
            if schedule_key in locked_lookup:
                schedule.is_locked = True

    return result


async def _persist_schedule_result(result: WeeklyScheduleResult, locked_shifts: list[dict] | None = None):
    await ScheduleRunDoc.find(ScheduleRunDoc.is_current == True).update_many(
        {"$set": {"is_current": False}}
    )

    locked_lookup = {}
    if locked_shifts:
        for ls in locked_shifts:
            key = (ls["employee_name"], ls["day_of_week"])
            locked_lookup[key] = set(ls["periods"])

    assignments = []
    for schedule in result.schedules:
        schedule_key = (schedule.employee_name, schedule.day_of_week)
        is_schedule_locked = schedule_key in locked_lookup
        locked_periods = locked_lookup.get(schedule_key, set())

        periods = [
            ShiftPeriodEmbed(
                period_index=p.period_index,
                start_time=p.start_time,
                end_time=p.end_time,
                scheduled=p.scheduled,
                is_locked=p.period_index in locked_periods if p.scheduled else False,
            )
            for p in schedule.periods
        ]
        assignments.append(
            Assignment(
                employee_name=schedule.employee_name,
                day_of_week=schedule.day_of_week,
                total_hours=schedule.total_hours,
                shift_start=schedule.shift_start,
                shift_end=schedule.shift_end,
                is_short_shift=schedule.is_short_shift,
                is_locked=is_schedule_locked,
                periods=periods,
            )
        )

    daily_summaries = []
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
        daily_summaries.append(
            DailySummary(
                day_of_week=summary.day_of_week,
                total_cost=summary.total_cost,
                employees_scheduled=summary.employees_scheduled,
                total_labor_hours=summary.total_labor_hours,
                dummy_worker_cost=summary.dummy_worker_cost,
                unfilled_periods=unfilled,
            )
        )

    schedule_run = ScheduleRunDoc(
        week_no=result.week_no,
        store_name=result.store_name,
        generated_at=datetime.fromisoformat(result.generated_at),
        total_weekly_cost=result.total_weekly_cost,
        total_dummy_worker_cost=result.total_dummy_worker_cost,
        total_short_shift_penalty=result.total_short_shift_penalty,
        status=result.status,
        has_warnings=result.has_warnings,
        is_current=True,
        daily_summaries=daily_summaries,
        assignments=assignments,
    )
    await schedule_run.insert()


@app.get("/schedule/results")
async def get_schedule_results() -> WeeklyScheduleResult | None:
    schedule_run = await ScheduleRunDoc.find_one(ScheduleRunDoc.is_current == True)

    if not schedule_run:
        return None

    return _schedule_run_to_result(schedule_run)


def _schedule_run_to_result(schedule_run: ScheduleRunDoc) -> WeeklyScheduleResult:
    from schemas import EmployeeDaySchedule, DayScheduleSummary, ShiftPeriod, UnfilledPeriod

    schedules = []
    for assignment in schedule_run.assignments:
        periods = [
            ShiftPeriod(
                period_index=p.period_index,
                start_time=p.start_time,
                end_time=p.end_time,
                scheduled=p.scheduled,
                is_locked=getattr(p, 'is_locked', False),
            )
            for p in assignment.periods
        ]
        schedules.append(
            EmployeeDaySchedule(
                employee_name=assignment.employee_name,
                day_of_week=assignment.day_of_week,
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
                total_cost=summary.total_cost,
                employees_scheduled=summary.employees_scheduled,
                total_labor_hours=summary.total_labor_hours,
                dummy_worker_cost=summary.dummy_worker_cost,
                unfilled_periods=unfilled,
            )
        )

    return WeeklyScheduleResult(
        week_no=schedule_run.week_no,
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

    return [
        {
            "id": str(run.id),
            "week_no": run.week_no,
            "store_name": run.store_name,
            "generated_at": run.generated_at.isoformat(),
            "total_weekly_cost": run.total_weekly_cost,
            "status": run.status,
            "has_warnings": run.has_warnings,
            "is_current": run.is_current,
        }
        for run in runs
    ]


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
    employees = await EmployeeDoc.find(EmployeeDoc.disabled == False).to_list()

    if not employees:
        return [e.model_dump() for e in data_import.employee]

    return [
        {
            "employee_name": e.employee_name,
            "hourly_rate": e.hourly_rate,
            "minimum_hours_per_week": e.minimum_hours_per_week,
            "minimum_hours": e.minimum_hours,
            "maximum_hours": e.maximum_hours,
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
    }


@app.post("/config")
async def update_config(
    dummy_worker_cost: float | None = None,
    short_shift_penalty: float | None = None,
    min_shift_hours: float | None = None,
    max_daily_hours: float | None = None,
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
            )
            for p in assignment.periods
        ]
        current_schedules.append(
            EDS(
                employee_name=assignment.employee_name,
                day_of_week=assignment.day_of_week,
                periods=periods,
                total_hours=assignment.total_hours,
                shift_start=assignment.shift_start,
                shift_end=assignment.shift_end,
                is_short_shift=assignment.is_short_shift,
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
            )
            for p in assignment.periods
        ]
        current_schedules.append(
            EDS(
                employee_name=assignment.employee_name,
                day_of_week=assignment.day_of_week,
                periods=periods,
                total_hours=assignment.total_hours,
                shift_start=assignment.shift_start,
                shift_end=assignment.shift_end,
                is_short_shift=assignment.is_short_shift,
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

    for schedule in current_schedules:
        if schedule.employee_name == request.employee_name and schedule.day_of_week == request.day_of_week:
            schedule_found = True

            if request.new_employee_name and request.new_employee_name != request.employee_name:
                # Reassigning to different employee - clear original
                updated_schedule = update_assignment_times(schedule, "00:00", "00:00", config)
                updated_schedules.append(updated_schedule)

                # Find or create target employee's schedule for that day
                target_found = False
                for target_schedule in current_schedules:
                    if target_schedule.employee_name == request.new_employee_name and target_schedule.day_of_week == request.day_of_week:
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
        elif request.new_employee_name and schedule.employee_name == request.new_employee_name and schedule.day_of_week == request.day_of_week:
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
            )
            for p in schedule.periods
        ]
        updated_assignments.append(
            Assignment(
                employee_name=schedule.employee_name,
                day_of_week=schedule.day_of_week,
                total_hours=schedule.total_hours,
                shift_start=schedule.shift_start,
                shift_end=schedule.shift_end,
                is_short_shift=schedule.is_short_shift,
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

    # Find and update the assignment
    assignment_found = False
    for assignment in schedule_run.assignments:
        if assignment.employee_name == request.employee_name and assignment.day_of_week == request.day_of_week:
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
            detail=f"No assignment found for {request.employee_name} on {request.day_of_week}"
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
                is_locked=p.is_locked,
            )
            for p in a.periods
        ]
        current_schedules.append(
            EDS(
                employee_name=a.employee_name,
                day_of_week=a.day_of_week,
                periods=periods,
                total_hours=a.total_hours,
                shift_start=a.shift_start,
                shift_end=a.shift_end,
                is_short_shift=a.is_short_shift,
                is_locked=a.is_locked,
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
