"""Location-scoped climate/soil integration.

This module deliberately does not borrow the pilot (Long Xuyen) artifacts for a
different point. Network fetching is opt-in via LOCATION_DATA_FETCH_ENABLED.
"""
from __future__ import annotations
import json, os, hashlib, csv
from dataclasses import dataclass
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
    try: return abs(float(a) - b) < 1e-6
    except (TypeError, ValueError): return False

def _read(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, UnicodeError, json.JSONDecodeError): return None

def load_location(root: Path, latitude: float, longitude: float) -> LocationData:
    power = root / "data/processed/power"
    soil_path = root / "data/processed/soil/soilgrids_profile.json"
    climate = _read(power / "climate_summary.json")
    soil = _read(soil_path)
    warnings: list[str] = []
    if not climate or not isinstance(climate.get("location"), dict) or not _same(climate["location"].get("latitude"), latitude) or not _same(climate["location"].get("longitude"), longitude):
        climate = None
        warnings.append("No NASA POWER artifact is available for the requested coordinates; Long Xuyen data was not reused.")
    if not soil or not isinstance(soil.get("location"), dict) or not _same(soil["location"].get("latitude"), latitude) or not _same(soil["location"].get("longitude"), longitude):
        soil = None
        warnings.append("No SoilGrids artifact is available for the requested coordinates; soil data was not reused.")
    enabled = os.getenv("LOCATION_DATA_FETCH_ENABLED", "0").lower() in {"1", "true", "yes"}
    location_dir = root / "data/processed/location_cache" / hashlib.sha256(f"{latitude:.6f},{longitude:.6f}".encode()).hexdigest()[:24]
    if enabled and (climate is None or soil is None):
        try:
            from datascience.power import fetch_location as fetch_power_location
            from datascience.soilgrids import fetch_location as fetch_soil_location
            start, end = os.getenv("LOCATION_CLIMATE_START", "20200101"), os.getenv("LOCATION_CLIMATE_END", "20251231")
            location_dir.mkdir(parents=True, exist_ok=True)
            climate = fetch_power_location(latitude, longitude, start, end, cache_dir=location_dir / ".cache")
            (location_dir / "climate_summary.json").write_text(json.dumps(climate), encoding="utf-8")
            with (location_dir / "nasa_power_daily.csv").open("w", newline="", encoding="utf-8") as handle:
                rows = climate.get("daily", []); writer = csv.DictWriter(handle, fieldnames=rows[0].keys() if rows else ["date"]); writer.writeheader(); writer.writerows(rows)
            soil = fetch_soil_location(latitude, longitude, cache_dir=location_dir / ".cache")
            (location_dir / "soilgrids_profile.json").write_text(json.dumps(soil), encoding="utf-8")
            daily = location_dir / "nasa_power_daily.csv"
            availability = {"climate": climate.get("availability", "unavailable"), "soil": soil.get("availability", "unavailable")}
            warnings.extend(climate.get("warnings", [])); warnings.extend(soil.get("warnings", []))
            return LocationData(climate if availability["climate"] != "unavailable" else None, daily, soil, availability, warnings)
        except Exception as exc:
            warnings.append(f"Location data integration failed: {type(exc).__name__}; no values were fabricated.")
    if not enabled:
        warnings.append("Location fetch is not enabled; run the DS NASA POWER/SoilGrids adapters for this location.")
    daily = power / "nasa_power_daily.csv" if climate and (power / "nasa_power_daily.csv").exists() else None
    climate_availability = climate.get("availability", "available") if climate else "unavailable"
    soil_availability = ("available" if soil.get("status") == "loaded" else "no_data") if soil else "unavailable"
    return LocationData(climate, daily, soil, {"climate": climate_availability, "soil": soil_availability}, warnings)
