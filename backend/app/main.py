import json, os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.models import RotationCompareResponse, RotationScenario
from app.services.decision import compare_rotation
app=FastAPI(title="TerraCycle AI API",version="1.0.0",description="Climate-adaptive crop rotation decision support; not a forecast")
app.add_middleware(CORSMiddleware,allow_origins=[v.strip() for v in os.getenv("CORS_ORIGINS","http://localhost:5173").split(",") if v.strip()],allow_methods=["GET","POST"],allow_headers=["Content-Type"])
ROOT=Path(__file__).resolve().parents[2]
@app.get("/health")
def health(): return {"status":"ok"}
@app.get("/api/climate/summary")
def climate_summary():
    path=ROOT/"data/processed/power/climate_summary.json"; fallback=ROOT/"shared/fixtures/climate-placeholder.json"; return json.loads((path if path.exists() else fallback).read_text(encoding="utf-8"))
@app.get("/api/crops")
def crops(): return json.loads((ROOT/"data/reference/crop_catalog.json").read_text(encoding="utf-8"))
@app.get("/api/soil/profile")
def soil_profile():
    path=ROOT/"data/processed/soil/soilgrids_profile.json"; return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"status":"unavailable","properties":[],"notes":["Run the SoilGrids adapter with coordinates; no values are fabricated."]}
@app.post("/api/rotations/compare",response_model=RotationCompareResponse)
def rotations_compare(request: RotationScenario): return compare_rotation(request)
