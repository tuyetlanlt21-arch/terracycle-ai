import json, logging, os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from app.models import DataSourceCatalog, RotationCompareBatchRequest, RotationCompareBatchResponse, RotationCompareResponse, RotationScenario
from app.services.decision import ClimateDataError, ReferenceDataError, compare_rotation, compare_rotations, validate_climate_summary, validate_crop_catalog
app=FastAPI(title="TerraCycle AI API",version="1.0.0",description="Climate-adaptive crop rotation decision support; not a forecast")

def parse_cors_origins(value: str | None) -> list[str]:
    return [origin.strip() for origin in (value or "").split(",") if origin.strip()]

ROOT=Path(__file__).resolve().parents[2]
logger=logging.getLogger(__name__)

def _read_reference_json(path: Path) -> dict:
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceDataError("reference dataset is unavailable or invalid") from exc
    if not isinstance(data,dict): raise ReferenceDataError("reference dataset must be a JSON object")
    return data

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    detail = [
        {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": detail})

@app.exception_handler(ClimateDataError)
async def climate_data_error_handler(request: Request, exc: ClimateDataError):
    logger.error("Historical climate summary is unavailable or invalid: %s",exc)
    return JSONResponse(status_code=503, content={"detail": "Climate summary data is unavailable."})

@app.exception_handler(ReferenceDataError)
async def reference_data_error_handler(request: Request, exc: ReferenceDataError):
    logger.error("Reference dataset is unavailable or invalid: %s",exc)
    return JSONResponse(status_code=503, content={"detail": "Reference data is unavailable."})

@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.error("Unhandled backend error for %s %s",request.method,request.url.path,exc_info=(type(exc),exc,exc.__traceback__))
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})

@app.get("/health")
def health(): return {"status":"ok"}
@app.get("/api/climate/summary")
def climate_summary(latitude: float = Query(..., ge=-90, le=90), longitude: float = Query(..., ge=-180, le=180)):
    from app.services.location_data import load_location
    located = load_location(ROOT, latitude, longitude)
    summary = located.climate
    if not isinstance(summary,dict): raise HTTPException(status_code=503,detail="Climate data is unavailable for the requested coordinates.")
    try:
        validate_climate_summary(summary)
    except ClimateDataError as exc:
        logger.error("Climate summary schema is invalid: %s",exc)
        raise HTTPException(status_code=503,detail="Climate summary data is unavailable.") from exc
    return summary
@app.get("/api/crops")
def crops():
    catalog=_read_reference_json(ROOT/"data/reference/crop_catalog.json")
    validate_crop_catalog(catalog)
    coefficients_path=ROOT/"data/reference/crop_coefficients.json"
    if coefficients_path.exists():
        coefficients=_read_reference_json(coefficients_path).get("records",{})
        if isinstance(coefficients,dict):
            for record in catalog.get("records",[]):
                record["fa056_crop_coefficient"]=coefficients.get(record.get("crop_id"))
    return catalog
@app.get("/api/soil/profile")
def soil_profile():
    path=ROOT/"data/processed/soil/soilgrids_profile.json"
    return _read_reference_json(path) if path.exists() else {"status":"unavailable","properties":[],"notes":["Run the SoilGrids adapter with coordinates; no values are fabricated."]}
@app.get("/api/data-sources",response_model=DataSourceCatalog)
def data_sources():
    raw=_read_reference_json(ROOT/"data/reference/data_sources.json")
    try:
        return DataSourceCatalog.model_validate(raw)
    except ValidationError as exc:
        logger.error("Data source catalog schema is invalid: %s",exc)
        raise ReferenceDataError("data source catalog is invalid") from exc
@app.post("/api/rotations/compare",response_model=RotationCompareResponse)
def rotations_compare(request: RotationScenario): return compare_rotation(request)

@app.post("/api/rotations/compare-all",response_model=RotationCompareBatchResponse)
def rotations_compare_all(request: RotationCompareBatchRequest):
    return {"results": compare_rotations(request.farm, request.candidate_crop_ids)}

# Keep CORS outside FastAPI's ServerErrorMiddleware so allowed browser origins
# can read the generic response when an unhandled server error occurs.
app = CORSMiddleware(
    app,
    allow_origins=parse_cors_origins(
        os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    ),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
