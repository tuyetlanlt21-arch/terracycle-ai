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

Current strategy is deterministic and **illustrative**; no probability or measured salt loss is inferred. Data comes from `shared/fixtures`.
