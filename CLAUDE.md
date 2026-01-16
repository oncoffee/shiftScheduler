# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Shift scheduling optimization application using Gurobi linear programming to generate cost-effective employee schedules. Full-stack app with Python/FastAPI backend and React/TypeScript frontend. Data is sourced from Google Sheets and persisted to MongoDB.

## Commands

### Backend (from `backend/` directory)
```bash
uv sync
uv run uvicorn app:app --reload
uv run pytest tests/ -v
```

### Frontend (from `frontend/` directory)
```bash
npm install
npm run dev
npm run build
npm run lint
```

### MongoDB (local development)
```bash
# Start MongoDB with Docker:
docker run -d -p 27017:27017 --name mongodb mongo:7
```

## Architecture

### Data Flow
```
Google Sheets (source of truth)
        │
        ▼ (POST /sync/all)
     MongoDB
        │
        ▼
   FastAPI API ──► React Frontend
        │
        ▼
   Gurobi Solver
```

### Backend Structure
1. **data_import.py** - Loads employees, stores, and availability from Google Sheets via gspread. Defines Pydantic models (`Store`, `Employee`, `EmployeeSchedule`).
2. **data_manipulation.py** - Transforms data into DataFrames with 30-minute time periods, merges employee availability with store hours.
3. **model_run.py** - Gurobi optimization model. Binary variables for scheduling, minimizes labor cost while enforcing staffing minimums, availability windows, shift continuity, and max hours.
4. **app.py** - FastAPI endpoints (see API Endpoints below).
5. **db/** - MongoDB integration layer:
   - `database.py` - MongoDB connection via Motor/Beanie ODM
   - `models.py` - Beanie document models (`EmployeeDoc`, `StoreDoc`, `ConfigDoc`, `ScheduleRunDoc`)
   - `sync.py` - Google Sheets → MongoDB sync logic

### Frontend Structure
- **api/client.ts** - Typed API client, uses `VITE_API_URL` env var (defaults to `http://localhost:8000`)
- **pages/** - Dashboard, Employees, Stores, Schedule (runs solver), Logs, Settings
- **components/ui/** - shadcn/ui components (Card, Button, Table, etc.)

### Optimization Model Key Constraints
- Employees scheduled only within their availability windows
- Minimum staffing per 30-minute period (varies by day: 2-4 workers)
- Max hours per employee per day (configurable, default 11)
- Minimum shift length (configurable, default 3 hours)
- Consecutive shifts only (no split shifts)
- Max 1 shift per day per employee

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/sync/all` | POST | Hot-load all data from Google Sheets to MongoDB |
| `/solver/run` | GET | Run Gurobi solver, persists result to MongoDB |
| `/schedule/results` | GET | Get current (most recent) schedule from MongoDB |
| `/schedule/history` | GET | List past solver runs |
| `/schedule/{id}` | GET | Get specific historical schedule by ID |
| `/employees` | GET | Get all enabled employees |
| `/stores` | GET | Get all stores with hours |
| `/schedules` | GET | Get employee availability |
| `/config` | GET | Get solver configuration |
| `/config` | POST | Update solver configuration (MongoDB only) |
| `/logs` | GET | Get application logs |

## Configuration

### Backend Environment (`.env`)
```
SERVICE_ACCOUNT_PATH=service_account.json
GOOGLE_SHEET_KEY=<sheet_id>
SOLVER_PASS_KEY=<password>
MONGODB_URL=mongodb://localhost:27017/shift_scheduler
```

### Frontend Environment
```
VITE_API_URL=http://localhost:8000
```

### Solver Settings (MongoDB config collection or Google Sheets Config tab)
- `dummy_worker_cost` - cost penalty for understaffing (default 100)
- `short_shift_penalty` - penalty for shifts under minimum length (default 50)
- `min_shift_hours` - minimum shift length in hours (default 3)
- `max_daily_hours` - maximum hours per employee per day (default 11)

## MongoDB Collections

| Collection | Purpose |
|------------|---------|
| `employees` | Employee docs with embedded availability array |
| `stores` | Store docs with embedded hours array |
| `config` | Single doc with solver settings |
| `schedule_runs` | Solver run history with embedded assignments & summaries |

## Key Files
- `backend/model_run.py` - Core Gurobi model with objective function and constraints
- `backend/data_import.py` - Google Sheets integration and Pydantic data models
- `backend/db/models.py` - Beanie ODM document models for MongoDB
- `backend/db/sync.py` - Google Sheets to MongoDB sync logic
- `frontend/src/api/client.ts` - API client with TypeScript interfaces
