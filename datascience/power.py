"""Reproducible NASA POWER daily ingestion and climate feature generation."""
from __future__ import annotations
import argparse, json, time, hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pandas as pd
import requests

ENDPOINT = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETERS = ("T2M", "T2M_MAX", "PRECTOTCORR", "RH2M", "ALLSKY_SFC_SW_DWN", "WS2M")
OUTPUT_COLUMNS = ["date", "latitude", "longitude", "temperature_avg_c", "temperature_max_c", "precipitation_mm_day", "relative_humidity_pct", "solar_radiation_kwh_m2_day", "wind_speed_m_s"]
PARAMETER_COLUMNS = {"T2M":"temperature_avg_c", "T2M_MAX":"temperature_max_c", "PRECTOTCORR":"precipitation_mm_day", "RH2M":"relative_humidity_pct", "ALLSKY_SFC_SW_DWN":"solar_radiation_kwh_m2_day", "WS2M":"wind_speed_m_s"}
UNITS = {"T2M":"C", "T2M_MAX":"C", "PRECTOTCORR":"mm/day", "RH2M":"%", "ALLSKY_SFC_SW_DWN":"kW-hr/m^2/day", "WS2M":"m/s"}

def build_params(latitude: float, longitude: float, start: str, end: str) -> dict[str, str]:
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180: raise ValueError("invalid coordinates")
    start_dt, end_dt = pd.to_datetime(start, format="%Y%m%d", errors="raise"), pd.to_datetime(end, format="%Y%m%d", errors="raise")
    if start_dt > end_dt: raise ValueError("start date must not be after end date")
    return {"latitude": str(latitude), "longitude": str(longitude), "start": start, "end": end, "community": "AG", "parameters": ",".join(PARAMETERS), "format": "JSON"}

def fetch_power(params: dict[str, str], timeout: float = 30, retries: int = 3, cache_dir: Path | None = None) -> dict[str, Any]:
    cache_path = None
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:20]
        cache_path = cache_dir / f"power_{key}.json"
        if cache_path.exists(): return json.loads(cache_path.read_text(encoding="utf-8"))
    last: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.get(ENDPOINT, params=params, timeout=timeout); response.raise_for_status(); payload = response.json()
            if not isinstance(payload.get("properties", {}).get("parameter"), dict): raise ValueError("Invalid NASA POWER response")
            if cache_path: cache_path.write_text(json.dumps(payload), encoding="utf-8")
            return payload
        except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
            last = exc
            if attempt + 1 < retries: time.sleep(2 ** attempt)
    raise RuntimeError(f"NASA POWER request failed after {retries} attempts: {last}") from last

def normalize(payload: dict[str, Any], requested_latitude: float | None = None, requested_longitude: float | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    values = payload["properties"]["parameter"]
    if any(not isinstance(values.get(p), dict) for p in PARAMETERS): raise ValueError("Missing required NASA POWER parameter")
    raw_dates = set().union(*(set(values[p]) for p in PARAMETERS)); coordinates = payload.get("properties", {}).get("coordinates") or {}
    point = payload.get("geometry", {}).get("coordinates", [])
    if not coordinates and len(point) >= 2: coordinates = {"longitude": point[0], "latitude": point[1]}
    coordinates = {"latitude": coordinates.get("latitude", requested_latitude), "longitude": coordinates.get("longitude", requested_longitude)}; rows = []
    for raw_day in sorted(raw_dates):
        row: dict[str, Any] = {"date": pd.to_datetime(raw_day, format="%Y%m%d", errors="raise").strftime("%Y-%m-%d"), "latitude": coordinates.get("latitude"), "longitude": coordinates.get("longitude")}
        for parameter in PARAMETERS:
            value = values[parameter].get(raw_day); row[PARAMETER_COLUMNS[parameter]] = None if value is None or float(value) in {-999.0, -9999.0} else float(value)
        rows.append(row)
    frame = pd.DataFrame(rows, columns=OUTPUT_COLUMNS).sort_values("date").reset_index(drop=True)
    if frame["relative_humidity_pct"].dropna().between(0, 100).eq(False).any(): raise ValueError("Relative humidity outside 0..100")
    for col in ["precipitation_mm_day", "solar_radiation_kwh_m2_day", "wind_speed_m_s"]:
        if (frame[col].dropna() < 0).any(): raise ValueError(f"Negative {col}")
    expected = pd.date_range(frame.date.min(), frame.date.max(), freq="D") if not frame.empty else pd.DatetimeIndex([]); present = set(frame.date); missing = [d.strftime("%Y-%m-%d") for d in expected if d.strftime("%Y-%m-%d") not in present]
    return frame, {"record_count": len(frame), "duplicate_dates": int(frame.date.duplicated().sum()), "missing_dates": missing, "missing_count": int(frame.isna().sum().sum()), "missing_by_column": frame.isna().sum().to_dict(), "units": UNITS}

def monthly_summary(frame: pd.DataFrame) -> pd.DataFrame:
    columns = ["month", "precipitation_sum_mm", "temperature_mean_c", "temperature_max_mean_c", "relative_humidity_mean_pct", "solar_radiation_mean_kwh_m2_day", "wind_speed_mean_m_s", "missing_count"]
    if frame.empty: return pd.DataFrame(columns=columns)
    f = frame.copy(); f["month"] = pd.to_datetime(f.date).dt.to_period("M").astype(str)
    result = f.groupby("month", as_index=False).agg(precipitation_sum_mm=("precipitation_mm_day", "sum"), temperature_mean_c=("temperature_avg_c", "mean"), temperature_max_mean_c=("temperature_max_c", "mean"), relative_humidity_mean_pct=("relative_humidity_pct", "mean"), solar_radiation_mean_kwh_m2_day=("solar_radiation_kwh_m2_day", "mean"), wind_speed_mean_m_s=("wind_speed_m_s", "mean"))
    result["missing_count"] = f.groupby("month")[OUTPUT_COLUMNS[3:]].apply(lambda x: int(x.isna().sum().sum())).values; return result[columns]

def seasonal_features(monthly: pd.DataFrame) -> dict[str, Any]:
    if monthly.empty: return {}
    month = pd.to_datetime(monthly.month + "-01").dt.month; seasons = {"dry":[12,1,2,3], "transition":[4,5,10,11], "wet":[6,7,8,9]}
    result = {}
    for name, months in seasons.items():
        selected = monthly.loc[month.isin(months)]
        if selected.empty: continue
        rain = selected["precipitation_sum_mm"]
        result[name] = {"precipitation_sum_mm_mean": float(rain.mean()), "precipitation_sum_mm_total": float(rain.sum()), "temperature_mean_c": float(selected["temperature_mean_c"].mean()), "temperature_max_mean_c": float(selected["temperature_max_mean_c"].mean()), "relative_humidity_mean_pct": float(selected["relative_humidity_mean_pct"].mean()), "dry_month_count": int((rain < 100).sum()), "rainfall_cv": float(rain.std(ddof=0) / rain.mean()) if rain.mean() else None, "heat_stress_month_count": int((selected["temperature_max_mean_c"] >= 35).sum())}
    result["indicators"] = {"dry_season_definition": "monthly precipitation <100 mm", "heat_stress_definition": "monthly mean daily maximum temperature >=35 C", "climate_indicators_are_derived_observations": True}
    return result

def run(latitude: float, longitude: float, start: str, end: str, output_dir: Path) -> dict[str, Any]:
    params = build_params(latitude, longitude, start, end); payload = fetch_power(params, cache_dir=output_dir / ".cache"); frame, quality = normalize(payload, latitude, longitude); monthly = monthly_summary(frame); output_dir.mkdir(parents=True, exist_ok=True); frame.to_csv(output_dir / "nasa_power_daily.csv", index=False); monthly.to_csv(output_dir / "climate_monthly.csv", index=False); (output_dir / "raw_response.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    summary = {"location":{"latitude":latitude,"longitude":longitude},"period":{"start":start,"end":end},"source":"NASA POWER","source_url":requests.Request("GET", ENDPOINT, params=params).prepare().url,"retrieval_date":datetime.now(timezone.utc).date().isoformat(),"units":UNITS,"daily_records":len(frame),"missing_count":quality["missing_count"],"quality":quality,"seasonal_features":seasonal_features(monthly),"monthly_metrics":monthly.to_dict(orient="records"),"forecast_available":False}
    (output_dir / "climate_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8"); return summary

def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("--latitude",type=float,default=10.41); p.add_argument("--longitude",type=float,default=106.96); p.add_argument("--start",default="20250101"); p.add_argument("--end",default="20251231"); p.add_argument("--output-dir",type=Path,default=Path("data/processed/power")); a=p.parse_args(); run(a.latitude,a.longitude,a.start,a.end,a.output_dir)
if __name__ == "__main__": main()
