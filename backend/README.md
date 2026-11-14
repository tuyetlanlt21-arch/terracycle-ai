# Backend module (Nhật Trường BE1, Minh Thắng BE2)

From repository root:

```bash
python -m venv .venv
# Activate .venv, then:
pip install -r backend/requirements.txt
PYTHONPATH=backend uvicorn app.main:app --reload --port 8000
```

Windows PowerShell: `$env:PYTHONPATH="backend"; uvicorn app.main:app --reload --port 8000`.

Docs: http://localhost:8000/docs | Health: http://localhost:8000/health

Tests: `PYTHONPATH=backend pytest backend/tests -q` (PowerShell: set PYTHONPATH first).

## BE-LOC-01 location contract

`POST /api/rotations/compare` accepts optional `farm.latitude` and
`farm.longitude`. They must be supplied together and are validated as
latitude `[-90, 90]`, longitude `[-180, 180]`; omitting both preserves the
legacy request contract.

When coordinates are supplied, climate and soil artifacts are accepted only
when their embedded location exactly matches the request. The response
provenance includes `evaluated_location`, per-source `availability`, and
location warnings (with `UNKNOWN` suitability when data is unavailable).
There is intentionally no Long Xuyen fallback. The DS `power.py` and
`soilgrids.py` adapters remain the ingestion boundary; enable deployment
fetching with `LOCATION_DATA_FETCH_ENABLED` only after wiring those adapters
and their cache directory. This backend does not infer regional agronomic
thresholds.

Current strategy is deterministic and **illustrative**; no probability or measured salt loss is inferred. Data comes from `shared/fixtures`.
