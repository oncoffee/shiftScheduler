from fastapi import FastAPI
from http.client import HTTPException

from model_run import main

app = FastAPI(title="shiftScheduler")

@app.get("solver/run")
async def run_ep(pass_key: str):
    if pass_key != "vero":
        raise HTTPException(401, "EP Failed")
    main()