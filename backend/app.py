import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from model_run import main
import data_import
from data_import import stores, employee, schedule
from schemas import WeeklyScheduleResult

load_dotenv()

SOLVER_PASS_KEY = os.getenv("SOLVER_PASS_KEY", "changeme")

app = FastAPI(title="shiftScheduler")

# In-memory cache for last schedule result
_last_schedule_result: WeeklyScheduleResult | None = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/solver/run", response_model=WeeklyScheduleResult)
async def run_ep(pass_key: str) -> WeeklyScheduleResult:
    global _last_schedule_result
    if pass_key != SOLVER_PASS_KEY:
        raise HTTPException(status_code=422, detail="Invalid Credentials")
    result = main()
    _last_schedule_result = result
    return result


@app.get("/schedule/results")
async def get_schedule_results() -> WeeklyScheduleResult | None:
    """Get the last generated schedule results"""
    return _last_schedule_result


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
def get_employees():
    return [e.model_dump() for e in employee]


@app.get("/stores")
def get_stores():
    return [s.model_dump() for s in stores]


@app.get("/schedules")
def get_schedules():
    return [s.model_dump() for s in schedule]


@app.get("/config")
def get_config():
    """Get current solver configuration"""
    # Reload to get latest from Google Sheets
    data_import.load_data()
    return data_import.config.model_dump()


@app.post("/config")
def update_config(
    dummy_worker_cost: float | None = None,
    short_shift_penalty: float | None = None,
    min_shift_hours: float | None = None,
    max_daily_hours: float | None = None,
):
    """Update solver configuration in Google Sheets"""
    import gspread

    try:
        worksheet = data_import.book.worksheet("Config")
    except gspread.exceptions.WorksheetNotFound:
        # Create the Config worksheet with default values
        worksheet = data_import.book.add_worksheet(title="Config", rows=10, cols=2)
        worksheet.update("A1:B5", [
            ["Setting", "Value"],
            ["dummy_worker_cost", 100],
            ["short_shift_penalty", 50],
            ["min_shift_hours", 3],
            ["max_daily_hours", 11],
        ])

    # Get current values
    rows = worksheet.get_all_records()
    setting_row_map = {}
    for idx, row in enumerate(rows, start=2):  # start=2 because row 1 is header
        setting_name = row.get("Setting")
        if setting_name:
            setting_row_map[setting_name] = idx

    updates = []
    if dummy_worker_cost is not None:
        if "dummy_worker_cost" in setting_row_map:
            updates.append({"range": f"B{setting_row_map['dummy_worker_cost']}", "values": [[dummy_worker_cost]]})
    if short_shift_penalty is not None:
        if "short_shift_penalty" in setting_row_map:
            updates.append({"range": f"B{setting_row_map['short_shift_penalty']}", "values": [[short_shift_penalty]]})
    if min_shift_hours is not None:
        if "min_shift_hours" in setting_row_map:
            updates.append({"range": f"B{setting_row_map['min_shift_hours']}", "values": [[min_shift_hours]]})
    if max_daily_hours is not None:
        if "max_daily_hours" in setting_row_map:
            updates.append({"range": f"B{setting_row_map['max_daily_hours']}", "values": [[max_daily_hours]]})

    if updates:
        worksheet.batch_update(updates)

    # Reload config to reflect changes
    data_import.load_data()

    return data_import.config.model_dump()
