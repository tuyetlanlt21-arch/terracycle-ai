"""Data-science-only sequence and strategy evaluation primitives.

This module deliberately does not replace the Backend contract. It provides
reusable, conservative assessments for notebooks, validation, and future API
integration. Unknown evidence is never converted into a pass.
"""
from __future__ import annotations
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any
import pandas as pd
from datascience.power import extract_growth_window

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data/reference/crop_catalog.json"
RULES_PATH = ROOT / "data/reference/rotation_rules.json"
STATUS = {"PASS", "FAIL", "UNKNOWN"}

def load_knowledge_base(catalog_path: Path = CATALOG_PATH, rules_path: Path = RULES_PATH) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8")); rules = json.loads(rules_path.read_text(encoding="utf-8"))
    records = {item["crop_id"]: item for item in catalog.get("records", [])}
    if set(records) != {"rice", "maize", "mung_bean", "soybean"}: raise ValueError("catalog must contain the four supported crops")
    return records, rules

def _status(values: list[str]) -> str:
    return "FAIL" if "FAIL" in values else "UNKNOWN" if "UNKNOWN" in values else "PASS"

def assess_climate_window(frame: pd.DataFrame, crop: dict[str, Any], planting_date: str | date | None) -> dict[str, Any]:
    duration = crop.get("growth_duration", {}).get("max_days")
    if planting_date is None: return {"status": "UNKNOWN", "reason": "planting date is required", "evidence": []}
    if not duration: return {"status": "UNKNOWN", "reason": "verified crop duration is unavailable", "evidence": []}
    window, coverage = extract_growth_window(frame, planting_date, int(duration))
    if window is None: return {"status": "UNKNOWN", "reason": coverage["reason"], "coverage": coverage, "evidence": []}
    temp = crop.get("temperature", {}); optimal = temp.get("optimal", {}); absolute = temp.get("absolute", {})
    mean_temp = float(window["temperature_avg_c"].mean()) if window["temperature_avg_c"].notna().all() else None
    max_temp = float(window["temperature_max_c"].max()) if window["temperature_max_c"].notna().all() else None
    if mean_temp is None or max_temp is None: status, reason = "UNKNOWN", "temperature observations are incomplete"
    elif mean_temp < absolute.get("min_c", float("-inf")) or mean_temp > absolute.get("max_c", float("inf")): status, reason = "FAIL", "mean temperature exceeds the sourced absolute range"
    elif optimal.get("min_c") is not None and optimal.get("max_c") is not None and optimal["min_c"] <= mean_temp <= optimal["max_c"]: status, reason = "PASS", "mean growth-window temperature is within the sourced optimal range"
    else: status, reason = "UNKNOWN", "mean temperature is outside optimal but inside the sourced absolute range"
    return {"status": status, "reason": reason, "coverage": coverage, "mean_temperature_c": mean_temp, "maximum_daily_temperature_c": max_temp, "rainfall_total_mm": float(window["precipitation_mm_day"].sum()) if window["precipitation_mm_day"].notna().all() else None, "rainfall_status": "UNKNOWN", "rainfall_reason": "catalog rainfall values are annual and cannot validate a seasonal rainfall window", "evidence": [temp.get("source_url")], "historical_observation_period": coverage["start"] + " to " + coverage["end"]}

def validate_sequence(sequence: list[dict[str, Any]], current_crop: str | None = None) -> dict[str, Any]:
    """Validate chronological, non-overlapping crop periods.

    Each item requires crop_id, planting_date and duration_days. Harvest dates
    are derived only from the supplied duration; no agronomic gap is invented.
    """
    if not sequence: return {"status": "UNKNOWN", "reasons": ["sequence is empty"]}
    reasons: list[str] = []; previous_end: pd.Timestamp | None = None
    for index, item in enumerate(sequence):
        if not item.get("crop_id") or not item.get("planting_date") or not item.get("duration_days"):
            reasons.append(f"sequence item {index} lacks crop_id, planting_date, or duration_days"); continue
        start = pd.Timestamp(item["planting_date"]).normalize(); end = start + pd.Timedelta(days=int(item["duration_days"]) - 1)
        if previous_end is not None and start <= previous_end: reasons.append(f"crop at position {index} overlaps the preceding crop period")
        previous_end = end
    return {"status": "FAIL" if reasons else "PASS", "reasons": reasons, "current_crop_checked": current_crop}

def assess_sequence(sequence: list[dict[str, Any]], farm: dict[str, Any], climate_frame: pd.DataFrame) -> dict[str, Any]:
    records, rules = load_knowledge_base(); chronology = validate_sequence(sequence, farm.get("current_crop")); reasons = list(chronology["reasons"]); assessments = []
    if chronology["status"] == "FAIL": return {"status": "FAIL", "score": None, "reasons": reasons, "assessments": assessments, "evidence": []}
    current = farm.get("current_crop")
    for item in sequence:
        crop_id = item.get("crop_id")
        if crop_id not in records: reasons.append(f"unsupported crop: {crop_id}"); continue
        crop = records[crop_id]; climate = assess_climate_window(climate_frame, crop, item.get("planting_date")); assessments.append({"crop_id": crop_id, "climate": climate})
        if climate["status"] == "FAIL": reasons.append(f"{crop_id}: {climate['reason']}")
    transitions = rules.get("compatibility", [])
    for previous, next_item in zip(sequence, sequence[1:]):
        target = next_item.get("crop_id"); source = previous.get("crop_id"); match = any(rule.get("from") == source and rule.get("to") == target for rule in transitions)
        if source != target and not match and not (source in {"mung_bean", "soybean"} and any(rule.get("from") == "legume" and rule.get("to") == target for rule in transitions)): reasons.append(f"no supported transition from {source} to {target}")
    status = "FAIL" if reasons else "UNKNOWN" if any(a["climate"]["status"] == "UNKNOWN" for a in assessments) else "PASS"
    return {"status": status, "score": None, "reasons": reasons, "assessments": assessments, "evidence": sorted({source for a in assessments for source in a["climate"].get("evidence", []) if source})}

def rank_strategy(crop_ids: list[str], strategy: str, farmer_priority: str, records: dict[str, dict[str, Any]], current_crop: str | None = None) -> list[str]:
    """Rank candidates by sourced metadata only; hard feasibility remains separate."""
    if strategy == "current_practice": key = lambda crop: (crop != current_crop, 0 if farmer_priority == "yield" and crop == current_crop else 1, crop)
    elif strategy == "water_saving":
        sensitivity = {"low": 0, "low-medium": 1, "medium": 2, "medium-high": 3, "high": 4, "unknown": 5}
        key = lambda crop: (sensitivity.get(records[crop].get("water_requirement", {}).get("drought_sensitivity", "unknown"), 5), crop)
    elif strategy == "soil_recovery": key = lambda crop: (not records[crop].get("legume", {}).get("is_legume", False), crop)
    else: raise ValueError(f"unsupported strategy: {strategy}")
    return sorted(crop_ids, key=key)
