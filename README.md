# Shift Scheduler

A shift scheduling optimization tool that uses Gurobi to generate cost-effective employee schedules while respecting availability constraints.

## What it does

The scheduler pulls employee availability and store hours from Google Sheets, then uses linear programming to find the optimal schedule that:

- Minimizes total labor costs
- Ensures minimum staffing levels are met
- Respects each employee's availability
- Keeps shifts consecutive (no split shifts)
- Enforces min/max hours per employee

## Project Structure

```
shiftScheduler/
├── backend/          # FastAPI + Gurobi solver
│   ├── app.py        # API endpoints
│   ├── model_run.py  # Optimization model
│   ├── data_import.py
│   └── tests/
├── frontend/         # React + Vite dashboard
│   └── src/
└── README.md
```

## Setup

### Backend

Requires Python 3.12+ and a Gurobi license.

```bash
cd backend

# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Copy the example env file and fill in your values
cp .env.example .env

# Run the server
uv run uvicorn app:app --reload
```

You'll need to set up:
- A Google service account with access to your scheduling spreadsheet
- Your Google Sheet key in the .env file
- A password for the solver endpoint

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 to view the dashboard.

## API Endpoints

- `GET /employees` - List all employees
- `GET /stores` - List store configurations
- `GET /schedules` - List employee availability
- `GET /solver/run?pass_key=xxx` - Run the optimizer
- `GET /logs` - View solver output

## Running Tests

```bash
cd backend
uv run pytest tests/ -v
```

## Tech Stack

- Backend: FastAPI, Gurobi, Pandas, gspread
- Frontend: React, Vite, Tailwind CSS, shadcn/ui
- Package management: uv (backend), npm (frontend)
