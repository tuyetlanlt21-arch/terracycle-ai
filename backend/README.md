# Backend local setup

The backend uses Python 3.12 and the dependencies in `backend/requirements.txt`.
Run commands from the repository root so the application can find the packaged
datasets under `data/`.

## Windows PowerShell

```powershell
py -3.12 -m venv .venv
Copy-Item backend\.env.example backend\.env
$venvPython = ".venv\Scripts\python.exe"
& $venvPython -m pip install -r backend\requirements.txt
$env:PYTHONPATH = "backend"
& $venvPython -m uvicorn app.main:app --app-dir backend --env-file backend\.env --reload --host 127.0.0.1 --port 8000
```

If the Python launcher does not recognize 3.12, run `python --version` and use
`python -m venv .venv` only when it reports Python 3.12. To activate the
environment instead, run `.venv\Scripts\Activate.ps1` and replace `& $venvPython`
with `python`.

## Linux / macOS

```bash
python3.12 -m venv .venv
cp backend/.env.example backend/.env
.venv/bin/python -m pip install -r backend/requirements.txt
PYTHONPATH=backend .venv/bin/python -m uvicorn app.main:app --app-dir backend --env-file backend/.env --reload --host 127.0.0.1 --port 8000
```

The environment file is local configuration and must not be committed. Set
`CORS_ORIGINS` to a comma-separated list of exact frontend origins. For a hosted
deployment, set it in the platform environment rather than using localhost.

## Container image

Build from the repository root so the image can include the backend and its
runtime datasets:

```powershell
docker build -f backend/Dockerfile -t terracycle-ai-backend .
docker run --rm -p 8000:8000 -e PORT=8000 -e CORS_ORIGINS=http://localhost:5173 terracycle-ai-backend
```

The image contains the crop catalog, rotation rules, NASA POWER daily CSV and
summary, soil profile, and climate fallback fixture. It runs as a non-root user.
The container health check calls `/health`; hosted platforms should also use
`/health` as their HTTP health-check path and provide `PORT` and
`CORS_ORIGINS` through platform environment settings.

## Verify

- Open API docs at <http://localhost:8000/docs>.
- `GET http://localhost:8000/health` returns `{"status":"ok"}`.
- `GET http://localhost:8000/api/climate/summary` returns the packaged
  historical climate summary.
- `POST http://localhost:8000/api/rotations/compare` compares a request using
  the crop catalog, rotation rules and NASA POWER daily CSV packaged under
  `data/`.

The rotation strategy is deterministic and illustrative. NASA POWER is
historical climate context, not a weather forecast; unknown field measurements
remain unknown.

## Tests

From the repository root:

```powershell
$env:PYTHONPATH = "backend"
$venvPython = ".venv\Scripts\python.exe"
& $venvPython -m pytest backend\tests -q
```

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q
```
