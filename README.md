# Shift Scheduler

Shift scheduling optimization application. Pulls data from Google Sheets, generates cost-effective schedules that respect availability constraints and staffing minimums.

## Solvers

This application supports multiple optimization solvers:

| Solver | Type | License |
|--------|------|---------|
| **Gurobi** | Commercial | Requires a valid Gurobi license |
| **PuLP/CBC** | Open Source | Free (bundled with PuLP) |
| **Google OR-Tools** | Open Source | Apache 2.0 |

You can select the solver from the Settings page in the UI.

### Gurobi Licensing

Gurobi requires a valid license to run. Options include:

- **Academic License**: Free for students and faculty at degree-granting institutions. Register at [gurobi.com](https://www.gurobi.com/academia/academic-program-and-licenses/)
- **Cloud License**: Pay-as-you-go pricing
- **Commercial License**: Contact Gurobi for enterprise pricing

This project does not include or distribute any Gurobi license. You are responsible for obtaining and complying with Gurobi's licensing terms. Visit [gurobi.com/licensing](https://www.gurobi.com/solutions/licensing/) for details.

If you don't have a Gurobi license, use **PuLP/CBC** or **Google OR-Tools** instead.

## Setup

### Backend

Requires Python 3.12+.

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

## Disclaimer

This software is provided "as is", without warranty of any kind, express or implied. The author (oncoffee) is not liable for any damages, losses, or issues arising from the use of this software. Use at your own risk.

This project is not affiliated with or endorsed by Gurobi Optimization, LLC. Gurobi is a registered trademark of Gurobi Optimization, LLC.
