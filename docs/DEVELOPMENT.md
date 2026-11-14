# Getting started

## 1. API

From repository root, create a Python environment then install `backend/requirements.txt`. Run `PYTHONPATH=backend uvicorn app.main:app --reload --port 8000` (PowerShell: `$env:PYTHONPATH="backend"` before running).

## 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

On PowerShell use `Copy-Item .env.example .env`.

## 3. Tests

```bash
PYTHONPATH=backend:. pytest backend/tests datascience/tests -q
cd frontend && npm run build
```

## Parallel development

Use separate branches `feat/saltshift-fe`, `feat/saltshift-ds`, `feat/saltshift-be1`, `feat/saltshift-be2`; PR into this scaffold branch first, then merge to main after review. Never commit API keys or environment files.
