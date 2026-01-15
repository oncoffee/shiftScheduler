import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from model_run import main
from data_import import stores, employee, schedule

load_dotenv()

SOLVER_PASS_KEY = os.getenv("SOLVER_PASS_KEY", "changeme")

app = FastAPI(title="shiftScheduler")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/solver/run")
async def run_ep(pass_key: str):
    if pass_key != SOLVER_PASS_KEY:
        raise HTTPException(status_code=422, detail="Invalid Credentials")
    main()
    return "Model successfully ran :')"


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
