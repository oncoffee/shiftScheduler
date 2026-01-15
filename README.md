# Shift Scheduler

Shift scheduling optimization using Gurobi linear programming. Pulls data from Google Sheets, generates cost-effective schedules that respect availability constraints and staffing minimums.

## Setup

### Backend

Requires Python 3.12+ and a Gurobi license.

```bash
cd backend
uv sync
cp .env.example .env
uv run uvicorn app:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## API

- `GET /employees` - list all employees
- `GET /stores` - list store configurations
- `GET /schedules` - list employee availability
- `GET /solver/run?pass_key=xxx` - run the optimizer
- `GET /schedule/results` - get last generated schedule
- `GET /logs` - view solver output
- `GET /config` - get solver settings
- `POST /config` - update solver settings

## Tests

```bash
cd backend
uv run pytest tests/ -v
```
