import os
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from model_run import main
import data_import
from schemas import WeeklyScheduleResult
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
