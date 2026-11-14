"""NASA POWER daily point acquisition and quality-controlled normalization."""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
from typing import Any
import pandas as pd
import requests
import csv

ENDPOINT = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETERS = ("T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "RH2M", "ALLSKY_SFC_SW_DWN")
OUTPUT_COLUMNS = ["date", "latitude", "longitude", "temperature_avg_c", "temperature_max_c", "temperature_min_c", "precipitation_mm_day", "relative_humidity_pct", "solar_radiation_kwh_m2_day"]
PARAMETER_COLUMNS = dict(zip(PARAMETERS, OUTPUT_COLUMNS[3:]))

def parse_power_daily_csv(path: str | Path) -> list[dict]:
    """Backward-compatible parser for NASA POWER CSV exports."""
    with open(path, encoding="utf-8-sig", newline="") as source: lines = source.readlines()
    header = next((i for i, line in enumerate(lines) if line.strip().startswith("YEAR,MO,DY")), None)
    if header is None: raise ValueError("No NASA POWER daily CSV header found (YEAR,MO,DY)")
    result = []
    for row in csv.DictReader(lines[header:]):
        if not row.get("YEAR"): continue
        item = {"date": f'{int(row["YEAR"]):04d}-{int(row["MO"]):02d}-{int(row["DY"]):02d}'}
        for key in row:
            if key in {"YEAR", "MO", "DY"}: continue
            value = row[key]; item[key] = None if value in ("", "-999", "-999.0", "-9999", "-9999.0") else float(value)
        result.append(item)
    return result

def build_params(latitude: float, longitude: float, start: str, end: str) -> dict[str, str]:
    return {"latitude": str(latitude), "longitude": str(longitude), "start": start, "end": end, "community": "AG", "parameters": ",".join(PARAMETERS), "format": "JSON"}

def fetch_power(params: dict[str, str], timeout: float = 30, retries: int = 3) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.get(ENDPOINT, params=params, timeout=timeout); response.raise_for_status(); payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("properties"), dict) or not isinstance(payload["properties"].get("parameter"), dict): raise ValueError("NASA POWER response has invalid properties.parameter structure")
            return payload
        except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 < retries: time.sleep(2 ** attempt)
    raise RuntimeError(f"NASA POWER request failed after {retries} attempts: {last_error}") from last_error

def normalize(payload: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    props, values = payload["properties"], payload["properties"]["parameter"]; rows: dict[str, dict[str, Any]] = {}; missing = {-999.0, -9999.0}
    for parameter in PARAMETERS:
        if not isinstance(values.get(parameter), dict): raise ValueError(f"Missing parameter series: {parameter}")
        for raw_day, raw_value in values[parameter].items():
            day = pd.to_datetime(raw_day, format="%Y%m%d", errors="raise").strftime("%Y-%m-%d"); rows.setdefault(day, {"date": day})[parameter] = None if raw_value is None or float(raw_value) in missing else float(raw_value)
    frame = pd.DataFrame(rows.values()).sort_values("date").reset_index(drop=True)
    coordinates = props.get("coordinates", {})
    if not coordinates:
        point = payload.get("geometry", {}).get("coordinates", [])
        coordinates = {"longitude": point[0], "latitude": point[1]} if len(point) >= 2 else {}
    frame["latitude"] = coordinates.get("latitude"); frame["longitude"] = coordinates.get("longitude"); frame = frame.rename(columns=PARAMETER_COLUMNS)
    for column in OUTPUT_COLUMNS:
        if column not in frame: frame[column] = None
    frame = frame[OUTPUT_COLUMNS]; expected = {"T2M": "C", "T2M_MAX": "C", "T2M_MIN": "C", "PRECTOTCORR": "mm/day", "RH2M": "%", "ALLSKY_SFC_SW_DWN": "kW-hr/m^2/day"}
    sources = [props.get("parameter_metadata", {}), payload.get("header", {}).get("units", {}), payload.get("header", {}).get("parameter_metadata", {})]
    units = {key: next((source.get(key, {}).get("units") if isinstance(source.get(key), dict) else source.get(key) for source in sources if isinstance(source, dict) and (key in source or key in source.get("units", {}))), fallback) for key, fallback in expected.items()}
    if any(units[key] not in ("C", "°C") for key in ("T2M", "T2M_MAX", "T2M_MIN")): raise ValueError(f"Unexpected temperature units: {units}")
    if (frame["relative_humidity_pct"].dropna().between(0, 100) == False).any(): raise ValueError("Relative humidity outside 0..100")
    if (frame[["precipitation_mm_day", "solar_radiation_kwh_m2_day"]].dropna() < 0).any().any(): raise ValueError("Negative precipitation or solar radiation")
    return frame, {"units": units, "missing_values": sorted(missing), "record_count": len(frame), "duplicate_dates": int(frame.date.duplicated().sum()), "missing_by_column": frame.isna().sum().to_dict()}

def run(latitude: float, longitude: float, start: str, end: str, raw_path: Path, csv_path: Path, metadata_path: Path) -> pd.DataFrame:
    params = build_params(latitude, longitude, start, end); payload = fetch_power(params); frame, quality = normalize(payload)
    for path in (raw_path, csv_path, metadata_path): path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(payload, indent=2), encoding="utf-8"); frame.to_csv(csv_path, index=False); metadata_path.write_text(json.dumps({"endpoint": ENDPOINT, "request": params, "quality": quality}, indent=2), encoding="utf-8"); return frame

def main() -> None:
    p = argparse.ArgumentParser(description="Acquire NASA POWER daily weather data"); p.add_argument("--latitude", type=float, default=10.41); p.add_argument("--longitude", type=float, default=106.96); p.add_argument("--start", default="20250101"); p.add_argument("--end", default="20251231"); p.add_argument("--raw", type=Path, default=Path("data/raw/power/can_gio_2025.json")); p.add_argument("--csv", type=Path, default=Path("data/processed/power/can_gio_daily_2025.csv")); p.add_argument("--metadata", type=Path, default=Path("data/processed/power/metadata.json")); a = p.parse_args(); print(f"Wrote {len(run(a.latitude, a.longitude, a.start, a.end, a.raw, a.csv, a.metadata))} records to {a.csv}")
if __name__ == "__main__": main()
