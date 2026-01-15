# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Shift scheduling optimization application using Gurobi linear programming to generate cost-effective employee schedules. Full-stack app with Python/FastAPI backend and React/TypeScript frontend. Data is sourced from Google Sheets.

## Commands

### Backend (from `backend/` directory)
```bash
uv sync                              # Install dependencies
uv run uvicorn app:app --reload      # Start dev server (port 8000)
uv run pytest tests/ -v              # Run all tests
uv run pytest tests/test_api.py -v   # Run single test file
```

### Frontend (from `frontend/` directory)
```bash
npm install          # Install dependencies
npm run dev          # Start dev server (port 5173)
npm run build        # Production build
npm run lint         # Run ESLint
```

## Architecture

### Backend Data Flow
1. **data_import.py** - Loads employees, stores, and availability from Google Sheets via gspread. Defines Pydantic models (`Store`, `Employee`, `EmployeeSchedule`).
2. **data_manipulation.py** - Transforms data into DataFrames with 30-minute time periods, merges employee availability with store hours.
3. **model_run.py** - Gurobi optimization model. Binary variables for scheduling, minimizes labor cost while enforcing staffing minimums, availability windows, shift continuity, and max hours.
4. **app.py** - FastAPI endpoints: `/solver/run` (password-protected), `/logs`, `/employees`, `/stores`, `/schedules`.

### Frontend Structure
- **api/client.ts** - Typed API client, uses `VITE_API_URL` env var (defaults to `http://localhost:8000`)
- **pages/** - Dashboard, Employees, Stores, Schedule (runs solver), Logs, Settings
- **components/ui/** - shadcn/ui components (Card, Button, Table, etc.)

### Optimization Model Key Constraints
- Employees scheduled only within their availability windows
- Minimum staffing per 30-minute period (varies by day: 2-4 workers)
- Max 22 hours per employee per day
- Consecutive shifts only (no split shifts)
- Max 1 shift per day per employee

## Configuration

### Backend Environment (`.env`)
```
SERVICE_ACCOUNT_PATH=service_account.json
GOOGLE_SHEET_KEY=<sheet_id>
SOLVER_PASS_KEY=<password>
```

### Frontend Environment
```
VITE_API_URL=http://localhost:8000
```

## Key Files
- `backend/model_run.py` - Core Gurobi model with objective function and constraints
- `backend/data_import.py` - Google Sheets integration and Pydantic data models
- `frontend/src/api/client.ts` - API client with TypeScript interfaces
