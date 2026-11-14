"""Transparent MVP rule engine for historical salt-production risk assessment.

Thresholds and weights are hypotheses for product prototyping, not validated
scientific limits. This module does not forecast weather or invent salinity.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

STAGES = ("preparation", "evaporation", "crystallization", "harvesting")
CONFIG = {"status": "MVP_ASSUMPTION_REQUIRES_EXPERT_VALIDATION", "weights": {"rain_exposure": .55, "evaporation_conditions": .20, "production_vulnerability": .25}, "rain_thresholds_mm_day": {"low": 0.1, "moderate": 1.0, "high": 5.0, "critical": 10.0}, "stage_vulnerability": {"preparation": 20, "evaporation": 45, "crystallization": 80, "harvesting": 60}, "data_confidence_complete": 85, "data_confidence_semantics": "MVP data-quality score (0-100), not probability, forecast accuracy, or scientific confidence interval"}
REQUIRED = ("date", "precipitation_power_mm_day", "precipitation_imerg_mm_day", "precipitation_gldas_mm_day", "temperature_avg_c", "relative_humidity_pct", "solar_radiation_kwh_m2_day", "evapotranspiration_gldas_mm_day")

def _level(score: float) -> str:
    if score < 25: return "LOW"
    if score < 50: return "MODERATE"
    if score < 75: return "HIGH"
    return "CRITICAL"

def _rain_score(row: pd.Series) -> tuple[float, list[str]]:
    vals = {"POWER": float(row.precipitation_power_mm_day), "IMERG": float(row.precipitation_imerg_mm_day), "GLDAS": float(row.precipitation_gldas_mm_day)}
    source, amount = max(vals.items(), key=lambda item: item[1]); t = CONFIG["rain_thresholds_mm_day"]
    score = 100 if amount >= t["critical"] else 75 if amount >= t["high"] else 50 if amount >= t["moderate"] else 25 if amount >= t["low"] else 0
    return score, [f"Highest source rainfall: {source} {amount:.3f} mm/day"] if amount > t["low"] else ["All rainfall sources are at or below the MVP low-exposure threshold"]

def _evap_score(row: pd.Series) -> tuple[float, list[str]]:
    score, factors = 0.0, []
    if row.relative_humidity_pct >= 85: score += 40; factors.append("high relative humidity reduces drying support")
    elif row.relative_humidity_pct >= 75: score += 20; factors.append("moderately high relative humidity")
    if row.solar_radiation_kwh_m2_day < 12: score += 35; factors.append("low solar radiation")
    elif row.solar_radiation_kwh_m2_day < 16: score += 15; factors.append("moderate solar radiation")
    if row.evapotranspiration_gldas_mm_day < 2: score += 25; factors.append("low GLDAS modeled evapotranspiration")
    else: factors.append("GLDAS modeled evapotranspiration supports drying relative to MVP threshold")
    return min(score, 100), factors

def _recommendations(stage: str, level: str) -> list[str]:
    if level == "LOW": return [f"{stage}: continue routine observation; confirm conditions with local measurements before operational decisions."]
    actions = {"preparation": "delay exposing new brine only if local operations allow and recheck rainfall conditions", "evaporation": "consider temporary cover or protected storage where available and inspect concentration before proceeding", "crystallization": "protect crystallization beds from incoming rain where feasible and verify brine concentration before harvesting decisions", "harvesting": "consider postponing harvest or protecting harvested salt if rain is observed or expected locally"}
    return [f"{stage}: {actions[stage]}; this is a conditional precaution, not a guarantee of avoiding loss."]

def assess_row(row: pd.Series, stage: str, brine_salinity: float | None = None) -> dict[str, Any]:
    if stage not in STAGES: raise ValueError(f"Unknown production stage: {stage}")
    missing = [c for c in REQUIRED if c not in row.index or pd.isna(row[c])]
    if missing: return {"date": str(row.get("date", "")), "status": "INSUFFICIENT_DATA", "risk_score": None, "risk_level": None, "production_stage": stage, "contributing_factors": [f"missing required fields: {', '.join(missing)}"], "recommendations": ["Do not assign a risk level; obtain the missing source data or local observations."], "data_confidence": 0, "assessment_type": "historical", "salinity_used": False}
    numbers = pd.to_numeric(row[list(REQUIRED)[1:]], errors="coerce")
    if numbers.isna().any() or not np.isfinite(numbers.to_numpy()).all() or any(float(row[c]) < 0 for c in REQUIRED if "precipitation" in c or c == "evapotranspiration_gldas_mm_day"):
        raise ValueError(f"Invalid numeric values for {row.get('date', '')}")
    rain, rain_factors = _rain_score(row); evap, evap_factors = _evap_score(row); vuln = CONFIG["stage_vulnerability"][stage]; confidence = CONFIG["data_confidence_complete"]
    raw = CONFIG["weights"]["rain_exposure"] * rain + CONFIG["weights"]["evaporation_conditions"] * evap + CONFIG["weights"]["production_vulnerability"] * vuln
    score = round(raw * confidence / 100, 2)
    factors = rain_factors + evap_factors + [f"production-stage vulnerability weight for {stage}: {vuln}/100"]
    if brine_salinity is not None: factors.append("brine salinity supplied but not used: no validated salinity-risk rule is configured")
    return {"date": str(row.date), "status": "OK", "risk_score": score, "risk_level": _level(score), "production_stage": stage, "contributing_factors": factors, "recommendations": _recommendations(stage, _level(score)), "data_confidence": confidence, "data_confidence_type": "MVP_DATA_QUALITY_SCORE_NOT_PROBABILITY", "assessment_type": "historical", "salinity_used": False, "component_scores": {"rain_exposure": rain, "evaporation_conditions": evap, "production_vulnerability": vuln}, "assumptions": CONFIG["status"]}

def assess(frame: pd.DataFrame, stage: str, brine_salinity: float | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    results = [assess_row(row, stage, brine_salinity) for _, row in frame.iterrows()]
    report = {"assessment_type": "historical", "production_stage": stage, "configuration": CONFIG, "records": len(results), "insufficient_data_days": sum(x["status"] == "INSUFFICIENT_DATA" for x in results), "warnings": ["MVP thresholds require expert validation.", "Historical observations are not forecasts.", "No brine salinity was invented or used."]}
    return pd.DataFrame(results), report

def run(input_path: Path, output_dir: Path, stage: str) -> pd.DataFrame:
    frame = pd.read_csv(input_path); result, report = assess(frame, stage)
    out = output_dir / "processed" / "risk"; out.mkdir(parents=True, exist_ok=True)
    result.to_csv(out / "salt_risk_assessment.csv", index=False)
    report["output_schema"] = list(result.columns); report["input"] = str(input_path)
    (out / "salt_risk_report.json").write_text(json.dumps({"assessments": result.to_dict(orient="records"), "quality": report}, indent=2), encoding="utf-8")
    return result

def main() -> None:
    p = argparse.ArgumentParser(description="SaltShift historical rule-based risk assessment"); p.add_argument("--input", type=Path, default=Path("data/processed/integrated/saltshift_daily_features.csv")); p.add_argument("--output-dir", type=Path, default=Path("data")); p.add_argument("--stage", choices=STAGES, default="evaporation"); a = p.parse_args(); print(f"Wrote {len(run(a.input, a.output_dir, a.stage))} risk rows")
if __name__ == "__main__": main()
