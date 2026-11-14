"""Time-basis-aware, evidence-driven crop rotation assessment."""
from __future__ import annotations
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any
import pandas as pd
from app.models import RejectedAlternative, RotationCompareResponse, RotationRecommendation, RotationScenario

ROOT=Path(__file__).resolve().parents[3]; CATALOG=ROOT/"data/reference/crop_catalog.json"; RULES=ROOT/"data/reference/rotation_rules.json"; CLIMATE=ROOT/"data/processed/power/climate_summary.json"; DAILY=ROOT/"data/processed/power/nasa_power_daily.csv"; WEIGHTS={"temperature":0.4,"water":0.3,"soil":0.3}

def _load():
    catalog=json.loads(CATALOG.read_text(encoding="utf-8")); records={x["crop_id"]:x for x in catalog.get("records",[])}
    if set(records)!={"rice","maize","mung_bean","soybean"}: raise ValueError("verified crop catalog must contain all four pilot crops")
    return records,json.loads(RULES.read_text(encoding="utf-8")),json.loads(CLIMATE.read_text(encoding="utf-8"))

def _window(start: date|None, days: int|None) -> tuple[pd.DataFrame|None,str]:
    if start is None: return None,"planting_date is required for time-dependent climate suitability"
    if not days: return None,"verified growth duration is unavailable"
    if not DAILY.exists(): return None,"NASA POWER daily dataset is unavailable"
    frame=pd.read_csv(DAILY,parse_dates=["date"]); end=start+timedelta(days=days-1); selection=frame[(frame.date.dt.date>=start)&(frame.date.dt.date<=end)]
    if len(selection)!=days: return None,f"daily climate coverage is incomplete for {start.isoformat()} to {end.isoformat()}"
    return selection,""

def _range(value: float|None, optimal: dict, absolute: dict, low_key: str, high_key: str) -> tuple[str,str]:
    low,high=optimal.get(low_key),optimal.get(high_key); alow,ahigh=absolute.get(low_key),absolute.get(high_key)
    if value is None or low is None or high is None: return "UNKNOWN","value or threshold unavailable"
    if (alow is not None and value<alow) or (ahigh is not None and value>ahigh): return "FAIL",f"{value:.2f} is outside the absolute range"
    return ("PASS",f"{value:.2f} is within optimal range {low:g}-{high:g}") if low<=value<=high else ("UNKNOWN",f"{value:.2f} is outside optimal but inside absolute range")

def _transition(current,target,rules):
    if current==target:return "PASS","current practice continuation",[]
    matches=[x for x in rules.get("compatibility",[]) if (x["from"]==current or x["from"]=="legume" and current in {"mung_bean","soybean"}) and x["to"]==target]
    if not matches:return "FAIL",f"no supported transition rule from {current} to {target}",[]
    rule=matches[0]; return ("PASS" if rule["classification"]=="supported_candidate" else "UNKNOWN"),rule["classification"],rule.get("source_urls",[])

def _calendar(target,planting_date,rules):
    window=rules.get("planting_windows",{}).get(target)
    if planting_date is None:return "UNKNOWN","planting_date is missing",[]
    if not isinstance(window,list):return "UNKNOWN",(window or {}).get("note","verified planting window unavailable"),[(window or {}).get("source_url")] if (window or {}).get("source_url") else []
    sources=[x.get("source_url") for x in window if x.get("source_url")]; ok=any(x["start_month"]<=planting_date.month<=x["end_month"] for x in window)
    return ("PASS","planting date is inside verified planting window",sources) if ok else ("FAIL","planting date is outside verified planting windows",sources)

def compare_rotation(scenario: RotationScenario)->RotationCompareResponse:
    records,rules,summary=_load(); candidates=scenario.candidate_crop_ids or list(records); current=scenario.farm.current_crop.strip().lower().replace(" ","_"); daily_period=f"{summary['period']['start']}–{summary['period']['end']}"; recommendations=[]; rejected=[]; missing=[]
    for target in candidates:
        if target not in records:
            rejected.append(RejectedAlternative(crop_id=target,sequence=[current,target],eligibility="FAIL",reasons=["crop is absent from verified catalog"],sources=[]));continue
        crop=records[target]; sources=list(crop.get("source_references",[])); transition,transition_reason,transition_sources=_transition(current,target,rules); sources+=transition_sources; calendar,calendar_reason,calendar_sources=_calendar(target,scenario.farm.planting_date,rules); sources+=calendar_sources; frame,window_reason=_window(scenario.farm.planting_date,crop.get("growth_duration",{}).get("max_days"))
        temp=crop.get("temperature",{}); soil=crop.get("soil_ph",{}); warnings=[x for status,x in ((transition,transition_reason),(calendar,calendar_reason)) if status=="UNKNOWN"]; reasons=[transition_reason,calendar_reason]
        if frame is None: temperature_status="UNKNOWN"; temperature_reason=window_reason; rainfall_status="UNKNOWN"; rainfall_reason="growing-window precipitation unavailable or cannot be compared to annual reference"; missing += [f"{target}: {window_reason}"]
        else:
            temperature_status,temperature_reason=_range(float(frame.temperature_avg_c.mean()),temp.get("optimal",{}),temp.get("absolute",{}),"min_c","max_c"); rainfall_total=float(frame.precipitation_mm_day.sum()); rainfall_status="UNKNOWN"; rainfall_reason=f"growing-window precipitation is {rainfall_total:.2f} mm; catalog rainfall reference is annual and was not compared to this seasonal total"
        # Annual ECOCROP rainfall is context only; it is never used as a hard check for a growth window.
        rainfall_reference=crop.get("rainfall",{}); annual_note=f"annual rainfall reference: {rainfall_reference.get('optimal',{}).get('min_mm_year')}-{rainfall_reference.get('optimal',{}).get('max_mm_year')} mm/year; context only"
        if scenario.farm.soil_ph is None: soil_status,soil_reason="UNKNOWN","soil pH is missing; SoilGrids has no values"
        else: soil_status,soil_reason=_range(scenario.farm.soil_ph,soil.get("optimal",{}),soil.get("absolute",{}),"min","max")
        water=crop.get("water_requirement",{}); water_status="UNKNOWN"; water_reason="seasonal crop-water requirement is unavailable" if water.get("min_mm_season") is None else "irrigation demand cannot be inferred from rainfall; no field water-balance data supplied"
        if water.get("source_url"):sources.append(water["source_url"])
        statuses={transition,calendar,temperature_status,soil_status}; hard="FAIL" if "FAIL" in statuses else "UNKNOWN" if "UNKNOWN" in statuses or water_status=="UNKNOWN" else "PASS"; eligibility=hard; score=None
        for status,reason in [(temperature_status,temperature_reason),(rainfall_status,rainfall_reason),(soil_status,soil_reason),(water_status,water_reason)]:
            if status=="UNKNOWN": warnings.append(reason); missing.append(f"{target}: {reason}")
        if scenario.strategy=="current_practice" and target==current:reasons.append("baseline continuation of current practice")
        elif scenario.strategy=="water_saving":reasons.append("water-saving ranking uses sourced water metadata only; no precise water saving is claimed")
        elif scenario.strategy=="soil_recovery":reasons.append("soil-recovery ranking recognizes sourced legume characteristics only; benefit is conditional")
        rationale=reasons+[annual_note,temperature_reason,rainfall_reason,water_reason,soil_reason]; duration=crop.get("growth_duration",{}).get("max_days")
        item=RotationRecommendation(sequence=[current,target],crop_id=target,crop_name=crop["crop_name"],strategy=scenario.strategy,eligibility=eligibility,score=score,growth_duration_days=duration,hard_constraints_pass=hard,suitability={"temperature":temperature_status,"rainfall_window":rainfall_status,"water":water_status,"soil":soil_status},rationale=rationale,warnings=sorted(set(warnings)),sources=sorted(set(x for x in sources if x)))
        (recommendations if eligibility!="FAIL" else rejected).append(item if eligibility!="FAIL" else RejectedAlternative(crop_id=target,sequence=[current,target],eligibility="FAIL",reasons=rationale,sources=item.sources))
    if not recommendations:missing.append("No eligible or assessable alternatives were returned.")
    return RotationCompareResponse(recommendations=recommendations,rejected_alternatives=rejected,missing_data_warnings=sorted(set(missing)),warnings=["NASA POWER is historical climate context, not a future forecast.","Precipitation is not evapotranspiration or irrigation demand.","UNKNOWN is not PASS; null scores are intentional when suitability cannot be calculated."],provenance={"climate_source":"NASA POWER","climate_period":daily_period,"climate_source_url":summary.get("source_url",""),"soil_status":json.loads((ROOT/"data/processed/soil/soilgrids_profile.json").read_text(encoding="utf-8")).get("status","unavailable"),"forecast_available":False},scoring={"weights":WEIGHTS,"score_definition":"null unless all required time-window, water and soil dimensions are PASS","threshold_time_basis":{"crop_rainfall":"annual mm/year from ECOCROP; context only","crop_water_requirement":"growing-season mm/season from FAO; not irrigation demand"},"annual_rainfall_policy":"annual ECOCROP rainfall thresholds are context only; never compared with seasonal totals","window_rainfall_policy":"daily precipitation is summed over planting_date through verified growth duration; no water-demand claim"})
