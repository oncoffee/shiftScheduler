from fastapi import FastAPI
from http.client import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from model_run import main

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
    if pass_key != "vero":
        raise HTTPException(422, "Invalid Credentials")
    main()
    return "Model successfully ran :')"

@app.get("/logs")
def read_logs():
    try:
        with open("/home/swap/PycharmProjects/shiftScheduler/gurobi.log",
                  "r") as logfile:
            logs = logfile.read()
            return logs
    except FileNotFoundError:
        return "Log file not found"

