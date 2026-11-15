"""Location-scoped climate/soil integration.

This module deliberately does not borrow the pilot (Long Xuyen) artifacts for a
different point. Network fetching is automatic and remains cache-first.
"""
from __future__ import annotations
import json, os, hashlib, csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

@dataclass
class LocationData:
    climate: dict[str, Any] | None
    daily_path: Path | None
    soil: dict[str, Any] | None
    availability: dict[str, str]
    warnings: list[str]

def _same(a: Any, b: float) -> bool:
    # NASA POWER may return the nearest grid point rounded to 3 decimals.
    # This accepts provider rounding while keeping cache identities coordinate-scoped.
    try: return abs(float(a) - b) <= 0.001
    except (TypeError, ValueError): return False

def _read(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, UnicodeError, json.JSONDecodeError): return None

def configured_climate_period(*, today: date | None = None) -> tuple[str, str]:
    """Return the configured NASA POWER range, defaulting to a stable recent history window.

    NASA POWER daily values are near-real-time rather than forecast data. Keep a
    seven-day buffer and request only through the last fully completed month so
    the default cache key does not change every day.
    """
    current = today or date.today()
    cutoff = current - timedelta(days=7)
    end_default = (cutoff.replace(day=1) - timedelta(days=1)).strftime("%Y%m%d")
    start = os.getenv("LOCATION_CLIMATE_START", "20200101")
    end = os.getenv("LOCATION_CLIMATE_END") or end_default
    return start, end

def _valid_climate_artifact(climate: dict[str, Any] | None, latitude: float, longitude: float, start: str) -> bool:
    if not climate or not isinstance(climate.get("location"), dict): return False
    if not _same(climate["location"].get("latitude"), latitude) or not _same(climate["location"].get("longitude"), longitude): return False
    period = climate.get("period") or {}
    if period.get("start") and period["start"] > start: return False
    from datascience.power_parameters import PARAMETERS
    quality = climate.get("quality") or {}
    coverage = quality.get("coverage") or {}
    return set(climate.get("parameters", [])) == set(PARAMETERS) and coverage.get("valid") is True

def _find_cached_climate_artifact(root: Path, latitude: float, longitude: float, start: str) -> tuple[Path, dict[str, Any]] | None:
    cache_root = root / "data/processed/location_cache"
    candidates: list[tuple[str, Path, dict[str, Any]]] = []
    for summary_path in cache_root.glob("*/climate_summary.json"):
        climate = _read(summary_path)
        if not _valid_climate_artifact(climate, latitude, longitude, start): continue
        if not (summary_path.parent / "nasa_power_daily.csv").is_file(): continue
        period_end = (climate.get("period") or {}).get("end")
        if isinstance(period_end, str): candidates.append((period_end, summary_path.parent, climate))
    if not candidates: return None
    _, path, climate = max(candidates, key=lambda candidate: candidate[0])
    return path, climate

def load_location(root: Path, latitude: float, longitude: float) -> LocationData:
    power = root / "data/processed/power"
    soil_path = root / "data/processed/soil/soilgrids_profile.json"
    start, end = configured_climate_period()
    from datascience.power_parameters import PARAMETERS
    cache_identity = json.dumps({"latitude": round(latitude, 6), "longitude": round(longitude, 6), "start": start, "parameters": PARAMETERS, "dataset_version": "nasa-power-daily-v2"}, sort_keys=True)
    location_dir = root / "data/processed/location_cache" / hashlib.sha256(cache_identity.encode()).hexdigest()[:24]
    cached_artifact = _find_cached_climate_artifact(root, latitude, longitude, start)
    cached_dir = cached_artifact[0] if cached_artifact else None
    scoped_power = location_dir if (location_dir / "climate_summary.json").exists() else cached_dir or power
    scoped_soil = location_dir if (location_dir / "soilgrids_profile.json").exists() else None
    climate = _read(scoped_power / "climate_summary.json")
    soil = _read(scoped_soil / "soilgrids_profile.json") if scoped_soil else _read(soil_path)
    warnings: list[str] = []
    if not _valid_climate_artifact(climate, latitude, longitude, start):
        climate = None
        warnings.append("No complete NASA POWER artifact is available for the requested coordinates; data from another location was not reused.")
    if not soil or not isinstance(soil.get("location"), dict) or not _same(soil["location"].get("latitude"), latitude) or not _same(soil["location"].get("longitude"), longitude):
        soil = None
        warnings.append("No SoilGrids artifact is available for the requested coordinates; soil data was not reused.")
    enabled = os.getenv("LOCATION_DATA_FETCH_ENABLED", "1").lower() in {"1", "true", "yes"}
    climate_is_stale = bool(climate and (climate.get("period") or {}).get("end", "") < end)
    if enabled and (climate is None or climate_is_stale):
        try:
            # Prefer an authentic repository export when one is present for the
            # requested coordinate; this is an offline equivalent of retrieval.
            from datascience.power import normalize as normalize_power
            offline_export_loaded = False
            for export in sorted(root.glob("nasa_*.json")):
                payload = json.loads(export.read_text(encoding="utf-8"))
                frame, quality = normalize_power(payload, latitude, longitude)
                point_lat = float(frame["latitude"].dropna().iloc[0]) if frame["latitude"].notna().any() else None
                point_lon = float(frame["longitude"].dropna().iloc[0]) if frame["longitude"].notna().any() else None
                if point_lat is None or point_lon is None or not _same(point_lat, latitude) or not _same(point_lon, longitude): continue
                quality["coverage"] = __import__("datascience.power", fromlist=["validate_daily_frame"]).validate_daily_frame(frame, start, end)
                climate = {"location":{"latitude":point_lat,"longitude":point_lon},"period":{"start":frame.date.min().replace("-", ""),"end":frame.date.max().replace("-", "")},"parameters":list(PARAMETERS),"source":"NASA POWER offline export","source_url":f"https://power.larc.nasa.gov/ imported from {export.name}","daily":frame.to_dict(orient="records"),"quality":quality,"availability":"available" if quality["coverage"]["valid"] else "partial"}
                location_dir.mkdir(parents=True, exist_ok=True); (location_dir / "climate_summary.json").write_text(json.dumps(climate), encoding="utf-8")
                with (location_dir / "nasa_power_daily.csv").open("w", newline="", encoding="utf-8") as handle:
                    rows=climate["daily"]; writer=csv.DictWriter(handle, fieldnames=rows[0].keys() if rows else ["date"]); writer.writeheader(); writer.writerows(rows)
                scoped_power=location_dir; warnings.append(f"Loaded authentic NASA POWER offline export: {export.name}"); offline_export_loaded = True; break
            if not offline_export_loaded:
                from datascience.power import fetch_location as fetch_power_location
                location_dir.mkdir(parents=True, exist_ok=True)
                fetched = fetch_power_location(latitude, longitude, start, end, timeout=8, retries=1, cache_dir=location_dir / ".cache")
                if fetched.get("availability") != "unavailable" and _valid_climate_artifact(fetched, latitude, longitude, start):
                    climate = fetched
                    (location_dir / "climate_summary.json").write_text(json.dumps(climate), encoding="utf-8")
                    with (location_dir / "nasa_power_daily.csv").open("w", newline="", encoding="utf-8") as handle:
                        rows = climate.get("daily", []); writer = csv.DictWriter(handle, fieldnames=rows[0].keys() if rows else ["date"]); writer.writeheader(); writer.writerows(rows)
                    scoped_power = location_dir; warnings.extend(fetched.get("warnings", []))
                elif climate is not None:
                    warnings.append(f"NASA POWER refresh through {end} was incomplete; retained complete observations through {(climate.get('period') or {}).get('end')}.")
        except Exception as exc:
            warnings.append(f"NASA POWER retrieval failed for requested coordinates: {type(exc).__name__}; no values were fabricated.")
    if enabled and soil is None:
        try:
            from datascience.soilgrids import fetch_location as fetch_soil_location
            location_dir.mkdir(parents=True, exist_ok=True); soil = fetch_soil_location(latitude, longitude, timeout=8, retries=1, cache_dir=location_dir / ".cache")
            (location_dir / "soilgrids_profile.json").write_text(json.dumps(soil), encoding="utf-8"); warnings.extend(soil.get("warnings", []))
        except Exception as exc: warnings.append(f"SoilGrids retrieval failed for requested coordinates: {type(exc).__name__}; no values were fabricated.")
    daily = scoped_power / "nasa_power_daily.csv" if climate and (scoped_power / "nasa_power_daily.csv").exists() else None
    climate_availability = climate.get("availability", "available") if climate else "unavailable"
    soil_availability = ("available" if soil.get("status") == "loaded" else "no_data") if soil else "unavailable"
    return LocationData(climate, daily, soil, {"climate": climate_availability, "soil": soil_availability}, warnings)
