import os
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

load_dotenv()

SOLVER_PASS_KEY = os.getenv("SOLVER_PASS_KEY", "changeme")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


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

    result = main()
    await _persist_schedule_result(result)

    return result


async def _persist_schedule_result(result: WeeklyScheduleResult):
    await ScheduleRunDoc.find(ScheduleRunDoc.is_current == True).update_many(
        {"$set": {"is_current": False}}
    )

    assignments = []
    for schedule in result.schedules:
        periods = [
            ShiftPeriodEmbed(
                period_index=p.period_index,
                start_time=p.start_time,
                end_time=p.end_time,
                scheduled=p.scheduled,
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
        }
        for e in employees
    ]


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
                    "week_no": hours.week_no,
                    "store_name": store.store_name,
                    "day_of_week": hours.day_of_week,
                    "start_time": hours.start_time,
                    "end_time": hours.end_time,
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

    # Validate the change first
    target_employee = request.new_employee_name or request.employee_name
    is_valid, errors, _ = await validate_schedule_change(
        employee_name=target_employee,
        day_of_week=request.day_of_week,
        proposed_start=request.new_shift_start,
        proposed_end=request.new_shift_end,
        current_schedules=current_schedules,
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
    updated_summaries, total_cost, total_dummy, total_short_shift = await recalculate_schedule_costs(
        updated_schedules, current_summaries
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
