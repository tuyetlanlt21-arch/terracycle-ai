"""Reproducible NASA POWER daily ingestion and climate feature generation."""
from __future__ import annotations
import argparse, json, time, hashlib, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pandas as pd
import requests
from datascience.power_parameters import PARAMETERS

ENDPOINT = "https://power.larc.nasa.gov/api/temporal/daily/point"
OUTPUT_COLUMNS = ["date", "latitude", "longitude", "temperature_avg_c", "temperature_min_c", "temperature_max_c", "precipitation_mm_day", "relative_humidity_pct", "wind_speed_m_s", "solar_radiation_kwh_m2_day", "surface_pressure_kpa"]
PARAMETER_COLUMNS = {"T2M":"temperature_avg_c", "T2M_MIN":"temperature_min_c", "T2M_MAX":"temperature_max_c", "PRECTOTCORR":"precipitation_mm_day", "RH2M":"relative_humidity_pct", "WS2M":"wind_speed_m_s", "ALLSKY_SFC_SW_DWN":"solar_radiation_kwh_m2_day", "PS":"surface_pressure_kpa"}
UNITS = {"T2M":"C", "T2M_MIN":"C", "T2M_MAX":"C", "PRECTOTCORR":"mm/day", "RH2M":"%", "WS2M":"m/s", "ALLSKY_SFC_SW_DWN":"kW-hr/m^2/day", "PS":"kPa"}

def build_params(latitude: float, longitude: float, start: str, end: str) -> dict[str, str]:
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180: raise ValueError("invalid coordinates")
    start_dt, end_dt = pd.to_datetime(start, format="%Y%m%d", errors="raise"), pd.to_datetime(end, format="%Y%m%d", errors="raise")
    if start_dt > end_dt: raise ValueError("start date must not be after end date")
    return {"latitude": str(latitude), "longitude": str(longitude), "start": start, "end": end, "community": "AG", "parameters": ",".join(PARAMETERS), "format": "JSON"}

def build_download_url(latitude: float, longitude: float, start: str, end: str) -> str:
    """Return the exact NASA POWER URL for manual retrieval."""
    return requests.Request("GET", ENDPOINT, params=build_params(latitude, longitude, start, end)).prepare().url

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

def fetch_location(latitude: float, longitude: float, start: str, end: str, *, timeout: float = 30, retries: int = 3, cache_dir: Path | None = None) -> dict[str, Any]:
    """Fetch and normalize one location without changing Rotation Engine fields."""
    params = build_params(latitude, longitude, start, end)
    payload = fetch_power(params, timeout=timeout, retries=retries, cache_dir=cache_dir)
    frame, quality = normalize(payload, latitude, longitude)
    quality["coverage"] = validate_daily_frame(frame, start, end)
    return {"location": {"latitude": latitude, "longitude": longitude}, "period": {"start": start, "end": end}, "parameters": list(PARAMETERS), "source": "NASA POWER", "source_url": requests.Request("GET", ENDPOINT, params=params).prepare().url, "retrieval_date": datetime.now(timezone.utc).date().isoformat(), "daily": frame.to_dict(orient="records"), "quality": quality, "availability": "available" if quality["coverage"]["valid"] else "partial", "warnings": [] if quality["coverage"]["valid"] else ["NASA POWER daily coverage is incomplete or contains missing observations."]}

def import_power_export(source: Path, output_dir: Path) -> dict[str, Any]:
    """Import an authentic NASA POWER JSON or CSV export offline.

    The source is never synthesized: JSON must contain POWER's parameter
    object, while CSV must contain the normalized daily columns or POWER
    parameter names. The same normalization, missing-value, and coverage
    checks used by live ingestion are applied.
    """
    if source.suffix.lower() == ".json":
        payload = json.loads(source.read_text(encoding="utf-8")); frame, quality = normalize(payload)
    elif source.suffix.lower() == ".csv":
        text = source.read_text(encoding="utf-8-sig")
        coordinate_match = re.search(r"Location:\s*latitude\s+([-+]?\d+(?:\.\d+)?)\s+longitude\s+([-+]?\d+(?:\.\d+)?)", text, re.IGNORECASE)
        header_line = next((index for index, line in enumerate(text.splitlines()) if line.strip().upper().startswith("YEAR,DOY,")), None)
        if header_line is None: raise ValueError("NASA POWER CSV is missing the YEAR,DOY header")
        raw = pd.read_csv(source, skiprows=header_line)
        if {"YEAR", "DOY"}.issubset(raw.columns):
            raw["date"] = pd.to_datetime(raw["YEAR"].astype(str) + raw["DOY"].astype(str).str.zfill(3), format="%Y%j", errors="coerce")
            if raw["date"].isna().any(): raise ValueError("NASA POWER CSV contains invalid YEAR/DOY values")
            raw = raw.drop(columns=["YEAR", "DOY"])
        aliases = {"T2M":"temperature_avg_c","T2M_MIN":"temperature_min_c","T2M_MAX":"temperature_max_c","PRECTOTCORR":"precipitation_mm_day","RH2M":"relative_humidity_pct","ALLSKY_SFC_SW_DWN":"solar_radiation_kwh_m2_day","WS2M":"wind_speed_m_s","PS":"surface_pressure_kpa"}; raw = raw.rename(columns=aliases)
        if "solar_radiation_kwh_m2_day" in raw: raw["solar_radiation_kwh_m2_day"] = pd.to_numeric(raw["solar_radiation_kwh_m2_day"], errors="coerce") / 3.6
        if coordinate_match:
            raw["latitude"], raw["longitude"] = float(coordinate_match.group(1)), float(coordinate_match.group(2))
        missing = set(OUTPUT_COLUMNS) - set(raw.columns)
        if missing: raise ValueError("NASA POWER CSV is missing columns: " + ", ".join(sorted(missing)))
        frame = raw[OUTPUT_COLUMNS].copy()
        for column in OUTPUT_COLUMNS:
            if column not in {"date", "latitude", "longitude"}: frame[column] = pd.to_numeric(frame[column], errors="coerce").replace({-999.0: pd.NA, -9999.0: pd.NA})
        quality = {"record_count": len(frame), "missing_count": int(frame.isna().sum().sum()), "missing_by_column": frame.isna().sum().to_dict(), "missing_by_year": {str(year): int(group.isna().sum().sum()) for year, group in frame.assign(_year=pd.to_datetime(frame["date"]).dt.year).groupby("_year")}, "units": UNITS}
    else: raise ValueError("NASA POWER export must be JSON or CSV")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.strftime("%Y-%m-%d"); coverage = validate_daily_frame(frame); quality["coverage"] = coverage
    output_dir.mkdir(parents=True, exist_ok=True); frame.to_csv(output_dir / "nasa_power_daily.csv", index=False); monthly = monthly_summary(frame); monthly.to_csv(output_dir / "climate_monthly.csv", index=False)
    summary = {"location": {"latitude": frame["latitude"].dropna().iloc[0] if "latitude" in frame and frame["latitude"].notna().any() else None, "longitude": frame["longitude"].dropna().iloc[0] if "longitude" in frame and frame["longitude"].notna().any() else None}, "period": {"start": frame.date.min().replace("-", ""), "end": frame.date.max().replace("-", "")}, "parameters": list(PARAMETERS), "source": "NASA POWER offline export", "source_url": f"https://power.larc.nasa.gov/ ( imported from {source.name} )", "retrieval_date": datetime.now(timezone.utc).date().isoformat(), "units": UNITS, "daily_records": len(frame), "missing_count": quality["missing_count"], "availability": "partial" if quality["missing_count"] else "available", "quality": quality, "seasonal_features": seasonal_features(monthly), "seasonal_metrics": seasonal_historical_summary(frame).to_dict(orient="records"), "monthly_metrics": monthly_historical_summary(frame).to_dict(orient="records"), "forecast_available": False}
    (output_dir / "climate_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8"); return summary

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

def validate_daily_frame(frame: pd.DataFrame, start: str | None = None, end: str | None = None) -> dict[str, Any]:
    """Validate temporal coverage without imputing observations."""
    if frame.empty: return {"valid": False, "reason": "daily frame is empty", "missing_dates": []}
    dates = pd.to_datetime(frame["date"], errors="coerce")
    if dates.isna().any(): return {"valid": False, "reason": "invalid date value", "missing_dates": []}
    duplicate_dates = int(dates.duplicated().sum())
    requested_start = pd.to_datetime(start, format="%Y%m%d") if start else dates.min()
    requested_end = pd.to_datetime(end, format="%Y%m%d") if end else dates.max()
    expected = pd.date_range(requested_start, requested_end, freq="D")
    present = set(dates.dt.strftime("%Y-%m-%d")); missing = [day.strftime("%Y-%m-%d") for day in expected if day.strftime("%Y-%m-%d") not in present]
    return {"valid": duplicate_dates == 0 and not missing and dates.min() <= requested_start and dates.max() >= requested_end, "start": dates.min().strftime("%Y-%m-%d"), "end": dates.max().strftime("%Y-%m-%d"), "expected_record_count": len(expected), "record_count": len(frame), "duplicate_dates": duplicate_dates, "missing_dates": missing, "leap_days_present": any(day.month == 2 and day.day == 29 for day in dates)}

def extract_growth_window(frame: pd.DataFrame, planting_date: str | pd.Timestamp, duration_days: int) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    """Extract a real daily crop window, including December-January crossings."""
    if duration_days <= 0: return None, {"status": "UNKNOWN", "reason": "duration must be positive"}
    start = pd.Timestamp(planting_date).normalize(); end = start + pd.Timedelta(days=duration_days - 1)
    dates = pd.to_datetime(frame["date"], errors="coerce"); selected = frame.loc[(dates >= start) & (dates <= end)].copy()
    expected = pd.date_range(start, end, freq="D"); present = set(pd.to_datetime(selected["date"]).dt.strftime("%Y-%m-%d")) if not selected.empty else set(); missing = [day.strftime("%Y-%m-%d") for day in expected if day.strftime("%Y-%m-%d") not in present]
    if missing: return None, {"status": "UNKNOWN", "reason": "daily climate coverage is incomplete", "start": start.date().isoformat(), "end": end.date().isoformat(), "missing_dates": missing}
    return selected.sort_values("date").reset_index(drop=True), {"status": "PASS", "start": start.date().isoformat(), "end": end.date().isoformat(), "duration_days": duration_days, "crosses_calendar_year": start.year != end.year}

def monthly_summary(frame: pd.DataFrame) -> pd.DataFrame:
    columns = ["month", "precipitation_sum_mm", "temperature_mean_c", "temperature_max_mean_c", "relative_humidity_mean_pct", "solar_radiation_mean_kwh_m2_day", "wind_speed_mean_m_s", "missing_count"]
    if frame.empty: return pd.DataFrame(columns=columns)
    f = frame.copy(); f["month"] = pd.to_datetime(f.date).dt.to_period("M").astype(str)
    result = f.groupby("month", as_index=False).agg(precipitation_sum_mm=("precipitation_mm_day", lambda x: x.sum(min_count=1)), temperature_mean_c=("temperature_avg_c", "mean"), temperature_max_mean_c=("temperature_max_c", "mean"), relative_humidity_mean_pct=("relative_humidity_pct", "mean"), solar_radiation_mean_kwh_m2_day=("solar_radiation_kwh_m2_day", "mean"), wind_speed_mean_m_s=("wind_speed_m_s", "mean"))
    result["missing_count"] = f.groupby("month")[OUTPUT_COLUMNS[3:]].apply(lambda x: int(x.isna().sum().sum())).values; return result[columns]

def monthly_historical_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Return one rainfall total per year-month and the historical month mean."""
    if frame.empty: return pd.DataFrame(columns=["month", "year", "precipitation_sum_mm", "missing_count", "status", "historical_average_mm"])
    f=frame.copy(); f["date"]=pd.to_datetime(f["date"]); f["year"]=f.date.dt.year; f["month"]=f.date.dt.month
    result=f.groupby(["year","month"],as_index=False).agg(precipitation_sum_mm=("precipitation_mm_day",lambda x:x.sum(min_count=1)), missing_count=("precipitation_mm_day",lambda x:int(x.isna().sum())))
    result["status"]=result["missing_count"].eq(0).map({True:"PASS",False:"UNKNOWN"}); averages=result.loc[result.status=="PASS"].groupby("month")["precipitation_sum_mm"].mean().rename("historical_average_mm"); result=result.join(averages,on="month"); result["month"]=result["month"].map(lambda x:f"{int(x):02d}"); return result

def seasonal_historical_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Return seasonal totals by season-year plus complete-year historical means."""
    result=seasonal_summary(frame)
    if result.empty: result["historical_average_mm"]=[]; return result
    averages=result.loc[result.status=="PASS"].groupby("season")["precipitation_sum_mm"].mean().rename("historical_average_mm")
    return result.join(averages,on="season")

def seasonal_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Return rainfall totals for each calendar-year season, without imputing gaps."""
    columns = ["season_year", "season", "precipitation_sum_mm", "observation_count", "expected_day_count", "missing_count", "status"]
    if frame.empty: return pd.DataFrame(columns=columns)
    f = frame.copy(); f["date"] = pd.to_datetime(f["date"]); f["season"] = f["date"].dt.month.map(lambda m: "dry" if m in (12,1,2,3) else "transition" if m in (4,5,10,11) else "wet")
    f["season_year"] = f["date"].dt.year + ((f["season"] == "dry") & (f["date"].dt.month == 12)).astype(int)
    rows = []
    for (year, season), group in f.groupby(["season_year", "season"]):
        months = {"dry": (1, 2, 3, 12), "transition": (4, 5, 10, 11), "wet": (6, 7, 8, 9)}[season]
        expected = sum(int(pd.Period(f"{int(year) if month != 12 else int(year)-1}-{month:02d}").days_in_month) for month in months)
        observed = int(group["precipitation_mm_day"].notna().sum()); missing = expected - observed
        rows.append({"season_year": int(year), "season": season, "precipitation_sum_mm": group["precipitation_mm_day"].sum(min_count=1), "observation_count": observed, "expected_day_count": expected, "missing_count": max(missing, 0), "status": "PASS" if missing == 0 else "UNKNOWN"})
    return pd.DataFrame(rows, columns=columns).sort_values(["season_year", "season"]).reset_index(drop=True)

def historical_growing_period_rainfall(frame: pd.DataFrame, planting_date: str | pd.Timestamp, duration_days: int) -> dict[str, Any]:
    """Compute the requested window and complete equivalent calendar windows by year."""
    window, coverage = extract_growth_window(frame, planting_date, duration_days)
    result: dict[str, Any] = {"status": coverage["status"], "coverage": coverage, "rainfall_total_mm": None, "historical_totals_mm": [], "historical_average_mm": None}
    if window is None: return result
    rain = window["precipitation_mm_day"]
    if rain.isna().any(): result.update(status="UNKNOWN", reason="daily precipitation observations are incomplete"); return result
    result["rainfall_total_mm"] = float(rain.sum())
    start = pd.Timestamp(planting_date).normalize()
    dates = pd.to_datetime(frame["date"])
    for year in sorted(dates.dt.year.unique()):
        try:
            candidate_start = start.replace(year=int(year))
        except ValueError:
            # Equivalent Feb-29 windows do not exist in non-leap years.
            continue
        candidate_end = candidate_start + pd.Timedelta(days=duration_days - 1)
        selected = frame.loc[(dates >= candidate_start) & (dates <= candidate_end), "precipitation_mm_day"]
        expected = pd.date_range(candidate_start, candidate_end)
        if len(selected) == len(expected) and not selected.isna().any(): result["historical_totals_mm"].append({"year": int(year), "start": candidate_start.date().isoformat(), "end": candidate_end.date().isoformat(), "rainfall_total_mm": float(selected.sum())})
    if result["historical_totals_mm"]: result["historical_average_mm"] = float(pd.Series([x["rainfall_total_mm"] for x in result["historical_totals_mm"]]).mean())
    result["status"] = "PASS" if result["historical_average_mm"] is not None else "UNKNOWN"
    if result["historical_average_mm"] is None:
        result["reason"] = "no complete equivalent calendar periods with daily precipitation observations"
    return result

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
    params = build_params(latitude, longitude, start, end); payload = fetch_power(params, cache_dir=output_dir / ".cache"); frame, quality = normalize(payload, latitude, longitude); coverage = validate_daily_frame(frame, start, end); quality["coverage"] = coverage; monthly = monthly_summary(frame); output_dir.mkdir(parents=True, exist_ok=True); frame.to_csv(output_dir / "nasa_power_daily.csv", index=False); monthly.to_csv(output_dir / "climate_monthly.csv", index=False); (output_dir / "raw_response.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    summary = {"location":{"latitude":latitude,"longitude":longitude},"period":{"start":start,"end":end},"parameters":list(PARAMETERS),"source":"NASA POWER","source_url":requests.Request("GET", ENDPOINT, params=params).prepare().url,"retrieval_date":datetime.now(timezone.utc).date().isoformat(),"units":UNITS,"daily_records":len(frame),"missing_count":quality["missing_count"],"quality":quality,"seasonal_features":seasonal_features(monthly),"seasonal_metrics":seasonal_summary(frame).to_dict(orient="records"),"monthly_metrics":monthly.to_dict(orient="records"),"forecast_available":False}
    (output_dir / "climate_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8"); return summary

def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("--latitude",type=float); p.add_argument("--longitude",type=float); p.add_argument("--start",default="20250101"); p.add_argument("--end",default="20251231"); p.add_argument("--output-dir",type=Path,default=Path("data/processed/power")); p.add_argument("--import-export",type=Path); a=p.parse_args();
    if a.import_export: import_power_export(a.import_export,a.output_dir)
    elif a.latitude is None or a.longitude is None: p.error("--latitude and --longitude are required unless --import-export is used")
    else: run(a.latitude,a.longitude,a.start,a.end,a.output_dir)
if __name__ == "__main__": main()
