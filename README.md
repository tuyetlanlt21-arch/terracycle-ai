# TerraCycle AI

**Climate-adaptive crop rotation support grounded in historical climate data and local farming conditions.**

TerraCycle AI is a prototype for NASA Space Apps 2026 — Field Shift, with a pilot site in Long Xuyen, An Giang, Vietnam. It helps users compare crop rotation options, understand the evidence behind each assessment, and identify missing information before planting.

**[Explore the live demo on Vercel →](https://terracycle-ai.vercel.app/)**

## Features

- Enter a farm profile with the current crop, field area, planting date, and farming priority.
- Add local measurements such as soil pH, soil salinity, irrigation-water salinity, and water-management conditions.
- Compare three strategies: current practice (`current_practice`), water saving (`water_saving`), and soil recovery (`soil_recovery`).
- Assess crop growth windows against NASA POWER records and documented crop rules.
- Review assessment rationale, rejected options, data provenance, and `PASS`, `FAIL`, or `UNKNOWN` outcomes.

## Data and assessment scope

| Source | Role |
| --- | --- |
| NASA POWER | Historical temperature, precipitation, humidity, solar radiation, and wind. The interface uses the pilot dataset for 2020–2025. |
| ISRIC SoilGrids | Adapter for modeled soil properties, with explicit availability reporting when the source cannot provide data. |
| Crop catalog and rotation rules | Sourced records, thresholds, and rules in `data/reference/`. The ECOCROP adapter normalizes an export when one is supplied. |
| Farmer inputs and local measurements | Soil pH, soil salinity, irrigation-water salinity, and field conditions. |

NASA POWER provides **historical context, not a weather forecast**. Soil and irrigation-water salinity are never inferred from SoilGrids. Missing evidence remains `UNKNOWN`; the application does not fabricate scientific values.

The current strategies are deterministic and illustrative. Strategy names do not represent measured water savings or soil recovery. See [data sources and limitations](docs/data-sources.md) for details.

## Technology

- **Frontend:** React 18, TypeScript, Vite, Lucide React.
- **Backend:** Python 3.12, FastAPI, Pydantic, Uvicorn.
- **Data science:** pandas, requests, and NASA POWER, SoilGrids, and ECOCROP adapters.
- **Validation:** pytest, the Node.js test runner, and GitHub Actions.

## Project structure

```text
terracycle-ai/
├── frontend/       # Farm profile and strategy comparison interface
├── backend/        # FastAPI application, API contracts, and assessment logic
├── datascience/    # Data pipelines and crop rotation assessment
├── data/           # Reference and processed datasets
├── shared/         # Shared fixtures and data
├── docs/           # Architecture, development guides, and test reports
└── .github/        # CI and auto-merge workflows
```

## Local setup

Requirements: **Python 3.12**, **Node.js 22**, and **npm**. Run the following PowerShell commands from the repository root.

### 1. Start the backend

```powershell
py -3.12 -m venv .venv
Copy-Item backend/.env.example backend/.env
& .venv/Scripts/python.exe -m pip install -r backend/requirements.txt -r datascience/requirements.txt
& .venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --env-file backend/.env --reload --host 127.0.0.1 --port 8000
```

- API: <http://localhost:8000>
- Swagger UI: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

For Linux/macOS setup and Docker instructions, see [backend/README.md](backend/README.md).

### 2. Start the frontend

Open a second terminal:

```powershell
cd frontend
Copy-Item .env.example .env
npm ci
npm run dev
```

Open the URL printed by Vite, usually <http://localhost:5173>.

### 3. Compare strategies

1. Open **Farm Profile** and enter the current crop, field area, planting date, and priority.
2. Choose a planting date within the historical 2020–2025 period supported by the interface.
3. Add local measurements where available. Leave unknown values blank.
4. Select **Compare three strategies** and read the evidence for each option. `UNKNOWN` means more evidence is needed for an assessment.

## Deployment configuration

The frontend demo is hosted at **[terracycle-ai.vercel.app](https://terracycle-ai.vercel.app/)**. Deploy the backend separately to serve API requests.

| Component | Environment variable | Configuration |
| --- | --- | --- |
| Frontend | `VITE_API_BASE_URL` | Public HTTPS backend URL, set before building. Use `http://localhost:8000` locally. |
| Backend | `CORS_ORIGINS` | Comma-separated list of allowed frontend origins. For the demo, include `https://terracycle-ai.vercel.app`. |

Production frontend builds do not fall back to localhost. Store production configuration in the hosting platform's environment settings. Never commit `.env` files or API keys.

## Validation

After installing the dependencies above, run the Python tests from the repository root:

```powershell
& .venv/Scripts/python.exe -m pytest backend/tests datascience/tests -q
```

Run frontend tests and a production build:

```powershell
cd frontend
npm test
npm run build
```

GitHub Actions runs backend/data science tests, frontend tests, and a frontend build on pull requests and pushes to configured branches.

## Main API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Check service health |
| `GET` | `/api/crops` | Retrieve the crop catalog |
| `GET` | `/api/soil/profile` | Retrieve the soil profile and data availability |
| `GET` | `/api/climate/summary` | Retrieve the historical climate summary |
| `POST` | `/api/rotations/compare` | Assess a strategy against a farm profile |

See Swagger UI for request and response schemas while the backend is running.

## Documentation

- [System architecture](docs/ARCHITECTURE.md)
- [Development guide](docs/DEVELOPMENT.md)
- [Backend setup and Docker](backend/README.md)
- [Data pipelines and assessment principles](datascience/README.md)
- [Data sources and limitations](docs/data-sources.md)
- [Shared data](shared/README.md)

## CI and opt-in auto-merge

Before using auto-merge, a repository administrator should configure `main` to require a pull request and the `backend` and `frontend` checks. Require branches to be up to date, preserve existing review requirements, and enable **Allow auto-merge** in repository settings.

Create the `automerge` label and apply it to a ready, same-repository PR targeting `main` while CI or a required review is pending. The workflow requests GitHub's native squash auto-merge. If the PR is already eligible to merge immediately, use GitHub's regular merge control. To cancel a registered request, select **Disable auto-merge** on the PR; removing the label alone does not cancel it.
