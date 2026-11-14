"""Deterministic validation/evaluation for evidence-backed rotation rules."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

REQUIRED_CROPS = {"rice", "maize", "mung_bean", "soybean"}

def load_catalog(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data.get("records")
    if data.get("status") == "unavailable_no_verified_export_in_repository" or not isinstance(records, list) or not records:
        raise ValueError("crop catalog is unavailable or empty")
    ids = {item.get("crop_id") for item in records}
    if ids != REQUIRED_CROPS: raise ValueError(f"catalog must contain exactly {sorted(REQUIRED_CROPS)}")
    for item in records:
        for section in ("temperature", "rainfall", "soil_ph", "growth_duration", "source_references"):
            if not item.get(section): raise ValueError(f"missing {section} for {item.get('crop_id')}")
    return data

def load_rules(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("compatibility") or not data.get("crop_constraints"): raise ValueError("rotation rules are incomplete")
    for rule in data["compatibility"]:
        if not rule.get("source_urls"): raise ValueError(f"rotation rule lacks source: {rule}")
    return data

def evaluate(rule: dict[str, Any], *, water_available: bool | None, soil_ph: float | None, soil_ec: float | None) -> dict[str, Any]:
    warnings=[]; hard_pass=True
    if water_available is None: warnings.append("water availability unknown")
    if soil_ph is None: warnings.append("soil pH unknown")
    if soil_ec is None: warnings.append("soil salinity EC unknown")
    if water_available is False and rule.get("requires_water_plan"): hard_pass=False
    return {"hard_constraints_pass": hard_pass, "warnings": warnings, "scoreable": hard_pass and not warnings}
