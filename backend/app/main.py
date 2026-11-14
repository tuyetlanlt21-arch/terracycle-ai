import json
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.models import CompareResponse, ScenarioRequest
from app.services.decision import compare_scenarios

app = FastAPI(title="SaltShift API", version="0.1.0", description="Illustrative salt-field triage API, not a weather forecast")
origins = [v.strip() for v in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if v.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
DATA = Path(__file__).resolve().parents[2] / "shared" / "fixtures"

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/demo", response_model=ScenarioRequest)
def demo():
    return ScenarioRequest.model_validate(json.loads((DATA / "demo-request.json").read_text(encoding="utf-8")))

@app.get("/api/climate/summary")
def climate_summary():
    return json.loads((DATA / "climate-placeholder.json").read_text(encoding="utf-8"))

@app.post("/api/scenarios/compare", response_model=CompareResponse)
def compare(request: ScenarioRequest):
    return compare_scenarios(request)

@app.post("/api/salt-fields/analyze", response_model=CompareResponse)
def analyze(request: ScenarioRequest):
    return compare_scenarios(request)
