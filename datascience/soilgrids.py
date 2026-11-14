"""ISRIC SoilGrids v2 point adapter; no fallback or fabricated measurements."""
from __future__ import annotations
import argparse, json, hashlib, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import requests

ENDPOINT = "https://rest.isric.org/soilgrids/v2.0/properties/query"
PROPERTIES = ("phh2o", "clay", "sand", "silt", "soc")
DEPTHS = ("0-5cm", "5-15cm", "15-30cm", "30-60cm")
SCALE = {"phh2o": 10, "clay": 10, "sand": 10, "silt": 10, "soc": 10}
UNITS = {"phh2o": "pH", "clay": "%", "sand": "%", "silt": "%", "soc": "g/kg"}

def fetch_soilgrids(latitude: float, longitude: float, timeout: float = 30, retries: int = 3, cache_dir: Path | None = None) -> dict[str, Any]:
    params = {"lon": longitude, "lat": latitude, "property": list(PROPERTIES), "depth": list(DEPTHS), "value": "mean"}
    cache_path = None
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:24]
        cache_path = cache_dir / f"soilgrids_{key}.json"
        if cache_path.exists(): return json.loads(cache_path.read_text(encoding="utf-8"))
    last = None
    for attempt in range(retries):
        try:
            response = requests.get(ENDPOINT, params=params, timeout=timeout); response.raise_for_status(); payload = response.json()
            if not isinstance(payload, dict) or "properties" not in payload: raise ValueError("Invalid SoilGrids response")
            if cache_path: cache_path.write_text(json.dumps(payload), encoding="utf-8")
            return payload
        except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
            last = exc
            if attempt + 1 < retries: time.sleep(2 ** attempt)
    raise RuntimeError(f"SoilGrids request failed after {retries} attempts: {last}") from last

def fetch_location(latitude: float, longitude: float, *, timeout: float = 30, retries: int = 3, cache_dir: Path | None = None) -> dict[str, Any]:
    try:
        result = normalize(fetch_soilgrids(latitude, longitude, timeout, retries, cache_dir), latitude, longitude)
        result["availability"] = "available" if result["status"] == "loaded" else "no_data"
        result["warnings"] = [] if result["status"] == "loaded" else ["SoilGrids returned no non-null values for this location."]
        return result
    except requests.RequestException as exc:
        return {"location":{"latitude":latitude,"longitude":longitude},"source":"ISRIC SoilGrids v2.0 REST API","source_url":ENDPOINT,"status":"network_error","availability":"unavailable","properties":[],"warnings":[f"SoilGrids network error: {exc}"]}
    except RuntimeError as exc:
        if isinstance(exc.__cause__, requests.RequestException):
            return {"location":{"latitude":latitude,"longitude":longitude},"source":"ISRIC SoilGrids v2.0 REST API","source_url":ENDPOINT,"status":"network_error","availability":"unavailable","properties":[],"warnings":[f"SoilGrids network error: {exc.__cause__}"]}
        return {"location":{"latitude":latitude,"longitude":longitude},"source":"ISRIC SoilGrids v2.0 REST API","source_url":ENDPOINT,"status":"unavailable","availability":"unavailable","properties":[],"warnings":[f"SoilGrids response unavailable: {exc}"]}
    except (ValueError, json.JSONDecodeError) as exc:
        return {"location":{"latitude":latitude,"longitude":longitude},"source":"ISRIC SoilGrids v2.0 REST API","source_url":ENDPOINT,"status":"unavailable","availability":"unavailable","properties":[],"warnings":[f"SoilGrids response unavailable: {exc}"]}

def normalize(payload: dict[str, Any], latitude: float, longitude: float) -> dict[str, Any]:
    layers = payload.get("properties", {}).get("layers", []); profile = []
    for layer in layers:
        name = layer.get("name"); measure = layer.get("unit_measure", {}); scale = measure.get("d_factor", SCALE.get(name, 1)); if_missing = {"property": name, "unit": measure.get("target_units") or UNITS.get(name), "scale_factor": scale, "values": {}}
        if name not in PROPERTIES: continue
        for depth in layer.get("depths", []):
            label = depth.get("label") or depth.get("name"); raw = depth.get("values", {}).get("mean")
            if label: if_missing["values"][label] = None if raw is None else raw / scale
        profile.append(if_missing)
    status = "loaded" if any(value is not None for item in profile for value in item["values"].values()) else "no_values"
    response_depths = sorted({label for item in profile for label in item["values"]}); null_count = sum(value is None for item in profile for value in item["values"].values())
    return {"location":{"latitude":latitude,"longitude":longitude},"source":"ISRIC SoilGrids v2.0 REST API","source_url":ENDPOINT,"retrieval_date":datetime.now(timezone.utc).date().isoformat(),"status":status,"diagnostics":{"requested_properties":list(PROPERTIES),"requested_depths":list(DEPTHS),"response_layers":[item["property"] for item in profile],"response_depths":response_depths,"null_value_count":null_count,"coverage_interpretation":"HTTP/JSON response contained the requested layers and depths, but all pixel means were null; this is retained as an unresolved coverage/service result, not converted to a measurement."},"properties":profile,"notes":["SoilGrids predictions are not farmer measurements.","Soil salinity EC and irrigation-water EC are intentionally absent and must be supplied separately.","Null values are returned by the service and were not imputed."]}

def run(latitude: float, longitude: float, output: Path) -> dict[str, Any]:
    try: result = normalize(fetch_soilgrids(latitude, longitude), latitude, longitude)
    except (requests.RequestException, ValueError) as exc:
        result = {"location":{"latitude":latitude,"longitude":longitude},"source":"ISRIC SoilGrids v2.0 REST API","source_url":ENDPOINT,"retrieval_date":datetime.now(timezone.utc).date().isoformat(),"status":"unavailable","error":str(exc),"properties":[],"notes":["No soil measurements were fabricated."]}
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, indent=2), encoding="utf-8"); return result

if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("--latitude",type=float,required=True); p.add_argument("--longitude",type=float,required=True); p.add_argument("--output",type=Path,default=Path("data/processed/soil/soilgrids_profile.json")); a=p.parse_args(); run(a.latitude,a.longitude,a.output)
