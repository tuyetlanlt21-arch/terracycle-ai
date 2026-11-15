"""Time-basis-aware, evidence-driven crop rotation assessment."""
from __future__ import annotations
import json
import math
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
import pandas as pd
from app.models import EvaluationResult, Provenance, RejectedAlternative, RotationCompareResponse, RotationRecommendation, RotationScenario, ScoringMetadata
from app.services.location_data import load_location
from datascience.evapotranspiration import reference_et0_fao56, crop_et_and_irrigation, effective_rainfall_scs

ROOT=Path(__file__).resolve().parents[3]; CATALOG=ROOT/"data/reference/crop_catalog.json"; COEFFICIENTS=ROOT/"data/reference/crop_coefficients.json"; RULES=ROOT/"data/reference/rotation_rules.json"; CLIMATE=ROOT/"data/processed/power/climate_summary.json"; DAILY=ROOT/"data/processed/power/nasa_power_daily.csv"; WEIGHTS={"temperature":0.4,"water":0.3,"soil":0.3}
SCORE_DEFINITION="null unless all required time-window, water and soil dimensions are PASS"
THRESHOLD_TIME_BASIS={"crop_rainfall":"annual mm/year from ECOCROP; context only","crop_water_requirement":"growing-season mm/season from FAO; not irrigation demand"}
ANNUAL_RAINFALL_POLICY="annual ECOCROP rainfall thresholds are context only; never compared with seasonal totals"
WINDOW_RAINFALL_POLICY="daily precipitation is summed over planting_date through verified growth duration; no water-demand claim"

class ClimateDataError(RuntimeError):
    """Historical climate summary data is missing or unusable."""

class ReferenceDataError(RuntimeError):
    """A required crop, rule, or soil reference dataset is missing or unusable."""

def _is_finite_number(value: Any) -> bool:
    if not isinstance(value,(int,float)) or isinstance(value,bool): return False
    try: return math.isfinite(value)
    except OverflowError: return False

def validate_crop_catalog(catalog: dict[str, Any]) -> None:
    records=catalog.get("records")
    if not isinstance(records,list): raise ReferenceDataError("crop catalog records must be a list")
    if any(not isinstance(record,dict) for record in records): raise ReferenceDataError("crop catalog records must be objects")
    if any(not isinstance(record.get("crop_id"),str) or not record["crop_id"].strip() for record in records): raise ReferenceDataError("crop catalog records require crop_id")
    if any(not isinstance(record.get("crop_name"),str) or not record["crop_name"].strip() for record in records): raise ReferenceDataError("crop catalog records require crop_name")
    if any(not isinstance(record.get("source_references",[]),list) or any(not isinstance(source,str) for source in record.get("source_references",[])) for record in records): raise ReferenceDataError("crop catalog source_references must be lists of strings")
    if any(not isinstance(record.get(key,{}),dict) for record in records for key in ("temperature","soil_ph","growth_duration","rainfall","water_requirement","soil_characteristics","legume")):
        raise ReferenceDataError("crop catalog assessment sections must be objects")
    for record in records:
        for section,keys in (("temperature",("min_c","max_c")),("soil_ph",("min","max"))):
            value=record.get(section,{})
            if any(not isinstance(value.get(bound,{}),dict) for bound in ("optimal","absolute")):
                raise ReferenceDataError(f"crop catalog {section} thresholds must be objects")
            for bound in ("optimal","absolute"):
                if any(key in value[bound] and value[bound][key] is not None and not _is_finite_number(value[bound][key]) for key in keys):
                    raise ReferenceDataError(f"crop catalog {section} thresholds must be finite numbers")
        duration=record.get("growth_duration",{})
        for key in ("min_days","max_days"):
            value=duration.get(key)
            if value is not None and (not isinstance(value,int) or isinstance(value,bool) or value<=0):
                raise ReferenceDataError("crop growth durations must be positive integer days or null")
        water=record.get("water_requirement",{})
        sensitivity=water.get("drought_sensitivity","unknown")
        if not isinstance(sensitivity,str) or sensitivity not in {"low","low-medium","medium","medium-high","high","unknown"}:
            raise ReferenceDataError("crop drought_sensitivity has an unsupported value")
        for key in ("min_mm_season","max_mm_season"):
            value=water.get(key)
            if value is not None and (not _is_finite_number(value) or value<0):
                raise ReferenceDataError("seasonal water requirements must be non-negative finite numbers or null")
        for section in ("temperature","soil_ph","growth_duration","water_requirement","soil_characteristics","legume"):
            value=record.get(section,{})
            if "source_url" in value and value["source_url"] is not None and not isinstance(value["source_url"],str):
                raise ReferenceDataError(f"crop catalog {section} source_url must be a string or null")

def validate_rotation_rules(rules: dict[str, Any]) -> None:
    applicability=rules.get("applicability")
    if not isinstance(applicability,dict) or applicability.get("type") != "verified_point_only" or not isinstance(applicability.get("supported_locations"),list):
        raise ReferenceDataError("rotation rules require verified applicability metadata")
    for point in applicability["supported_locations"]:
        if not isinstance(point,dict) or not isinstance(point.get("name"),str) or not _is_finite_number(point.get("latitude")) or not _is_finite_number(point.get("longitude")):
            raise ReferenceDataError("rotation rule supported locations are invalid")
        if not -90 <= point["latitude"] <= 90 or not -180 <= point["longitude"] <= 180: raise ReferenceDataError("rotation rule location is outside coordinate bounds")
    if not isinstance(applicability.get("unsupported_reason"),str) or not applicability["unsupported_reason"].strip(): raise ReferenceDataError("rotation rule applicability requires unsupported_reason")
    compatibility=rules.get("compatibility",[])
    if not isinstance(compatibility,list): raise ReferenceDataError("rotation compatibility rules must be a list")
    for rule in compatibility:
        if not isinstance(rule,dict) or any(not isinstance(rule.get(key),str) for key in ("from","to","classification")):
            raise ReferenceDataError("rotation compatibility entries require from, to, and classification")
        if not isinstance(rule.get("source_urls",[]),list) or any(not isinstance(source,str) for source in rule.get("source_urls",[])):
            raise ReferenceDataError("rotation rule source_urls must be lists of strings")
    windows=rules.get("planting_windows",{})
    if not isinstance(windows,dict): raise ReferenceDataError("planting_windows must be an object")
    for window in windows.values():
        if isinstance(window,list):
            for item in window:
                if not isinstance(item,dict) or type(item.get("start_month")) is not int or type(item.get("end_month")) is not int:
                    raise ReferenceDataError("planting window entries require start_month and end_month")
                if not 1<=item["start_month"]<=12 or not 1<=item["end_month"]<=12:
                    raise ReferenceDataError("planting window months must be between 1 and 12")
                if "source_url" in item and item["source_url"] is not None and not isinstance(item["source_url"],str):
                    raise ReferenceDataError("planting window source_url must be a string or null")
        elif not isinstance(window,dict):
            raise ReferenceDataError("planting window values must be objects or lists")
        else:
            if "source_url" in window and window["source_url"] is not None and not isinstance(window["source_url"],str):
                raise ReferenceDataError("planting window source_url must be a string or null")
            if "note" in window and window["note"] is not None and not isinstance(window["note"],str):
                raise ReferenceDataError("planting window note must be a string or null")

def validate_climate_summary(summary: dict[str, Any]) -> None:
    period=summary.get("period")
    if period is not None and (not isinstance(period,dict) or not isinstance(period.get("start"),str) or not isinstance(period.get("end"),str)):
        raise ClimateDataError("climate summary period must contain string start and end dates")
    if period is not None:
        try:
            start=datetime.strptime(period["start"],"%Y%m%d").date()
            end=datetime.strptime(period["end"],"%Y%m%d").date()
        except ValueError as exc:
            raise ClimateDataError("climate summary dates must use YYYYMMDD format") from exc
        if end<start: raise ClimateDataError("climate summary end date precedes start date")
    if "source_url" in summary and summary["source_url"] is not None and not isinstance(summary["source_url"],str):
        raise ClimateDataError("climate summary source_url must be a string")

def _provenance(summary: dict[str, Any], climate_period: str | None, location=None, availability=None, warnings=None, rules=None, applicability_reason=None) -> Provenance:
    soil_path=ROOT/"data/processed/soil/soilgrids_profile.json"
    try:
        soil_profile=json.loads(soil_path.read_text(encoding="utf-8")) if soil_path.exists() else {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceDataError("soil profile data is unavailable or invalid") from exc
    if not isinstance(soil_profile,dict): raise ReferenceDataError("soil profile data must be a JSON object")
    soil_status=("unavailable" if availability and availability.get("soil") != "available" else soil_profile.get("status","unavailable"))
    if soil_status is not None and not isinstance(soil_status,str): raise ReferenceDataError("soil profile status must be a string or null")
    applicability=(rules or {}).get("applicability",{})
    return Provenance(climate_source="NASA POWER",climate_period=climate_period,climate_source_url=summary.get("source_url") or None,soil_status=soil_status,forecast_available=False,evaluated_location=location,availability=availability or {},observation_time=summary.get("retrieval_date"),warnings=warnings or [],rule_set=f"rotation_rules.json@{(rules or {}).get('schema_version','unknown')}",supported_scope=applicability.get("type"),applicability_reason=applicability_reason)

def _scoring_metadata() -> ScoringMetadata:
    return ScoringMetadata(weights=WEIGHTS,score_definition=SCORE_DEFINITION,threshold_time_basis=THRESHOLD_TIME_BASIS,annual_rainfall_policy=ANNUAL_RAINFALL_POLICY,window_rainfall_policy=WINDOW_RAINFALL_POLICY)

def _load():
    try:
        catalog=json.loads(CATALOG.read_text(encoding="utf-8"))
        rules=json.loads(RULES.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceDataError("crop catalog or rotation rules are unavailable or invalid") from exc
    if not isinstance(catalog,dict): raise ReferenceDataError("crop catalog must be an object")
    validate_crop_catalog(catalog)
    try:
        records={x["crop_id"]:x for x in catalog["records"]}
    except (TypeError, KeyError) as exc:
        raise ReferenceDataError("crop catalog has an invalid schema") from exc
    if set(records)!={"rice","maize","mung_bean","soybean"}: raise ReferenceDataError("verified crop catalog must contain all four pilot crops")
    if not isinstance(rules,dict): raise ReferenceDataError("rotation rules must be an object")
    validate_rotation_rules(rules)
    # Climate is location-scoped and is loaded by compare_rotation through
    # load_location. Never require or reuse the repository-level pilot artifact.
    summary={}
    try:
        coefficients=json.loads(COEFFICIENTS.read_text(encoding="utf-8")).get("records",{}) if COEFFICIENTS.exists() else {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceDataError("crop coefficient catalog is unavailable or invalid") from exc
    for crop_id, record in records.items(): record["fa056_crop_coefficient"] = coefficients.get(crop_id)
    return records,rules,summary

def _window(start: date|None, days: int|None, daily_path: Path | None = None) -> tuple[pd.DataFrame|None,str]:
    daily_path = daily_path or DAILY
    if start is None: return None,"planting_date is required for time-dependent climate suitability"
    if not days: return None,"verified growth duration is unavailable"
    if not daily_path.exists(): return None,"NASA POWER daily dataset is unavailable"
    try:
        frame=pd.read_csv(daily_path)
    except (OSError, UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return None,"NASA POWER daily dataset could not be read"
    required={"date","temperature_avg_c","temperature_min_c","temperature_max_c",
              "relative_humidity_pct","wind_speed_m_s","solar_radiation_kwh_m2_day",
              "surface_pressure_kpa","precipitation_mm_day"}
    if "date" not in frame.columns: return None,"NASA POWER daily dataset is missing the required date column"
    missing_columns=required-set(frame.columns)
    if missing_columns: return None,"NASA POWER daily dataset is missing required climate columns: "+", ".join(sorted(missing_columns))
    frame["date"]=pd.to_datetime(frame["date"],errors="coerce")
    if frame["date"].isna().any(): return None,"NASA POWER daily dataset contains invalid dates"
    try:
        end=start+timedelta(days=days-1)
        expected_dates=set(pd.date_range(start=start,end=end).date)
    except (OverflowError, ValueError):
        return None,"daily climate date range cannot be represented"
    selection=frame[(frame.date.dt.date>=start)&(frame.date.dt.date<=end)]
    selected_dates=selection.date.dt.date
    if selected_dates.duplicated().any() or set(selected_dates)!=expected_dates:
        return None,f"daily climate coverage is incomplete for {start.isoformat()} to {end.isoformat()}"
    if selection[sorted(required-{"date"})].isna().any().any():
        return None,"NASA POWER daily climate window contains missing climate values"
    return selection.sort_values("date").reset_index(drop=True),""

def _range(value: float|None, optimal: dict, absolute: dict, low_key: str, high_key: str) -> tuple[str,str]:
    low,high=optimal.get(low_key),optimal.get(high_key); alow,ahigh=absolute.get(low_key),absolute.get(high_key)
    if value is None or low is None or high is None: return "UNKNOWN","value or threshold unavailable"
    if (alow is not None and value<alow) or (ahigh is not None and value>ahigh): return "FAIL",f"{value:.2f} is outside the absolute range"
    return ("PASS",f"{value:.2f} is within optimal range {low:g}-{high:g}") if low<=value<=high else ("UNKNOWN",f"{value:.2f} is outside optimal but inside absolute range")

def _transition(current,target,rules,applicable=True):
    if not applicable: return "UNKNOWN","rotation transition rules are outside their verified geographic scope",[]
    if current==target:return "PASS","current practice continuation",[]
    matches=[x for x in rules.get("compatibility",[]) if (x["from"]==current or x["from"]=="legume" and current in {"mung_bean","soybean"}) and x["to"]==target]
    if not matches:return "FAIL",f"no supported transition rule from {current} to {target}",[]
    rule=matches[0]; return ("PASS" if rule["classification"]=="supported_candidate" else "UNKNOWN"),rule["classification"],rule.get("source_urls",[])

def _calendar(target,planting_date,rules,applicable=True):
    if not applicable: return "UNKNOWN","seasonal calendar is outside the verified geographic scope",[]
    window=rules.get("planting_windows",{}).get(target)
    if planting_date is None:return "UNKNOWN","planting_date is missing",[]
    if not isinstance(window,list):return "UNKNOWN",(window or {}).get("note","verified planting window unavailable"),[(window or {}).get("source_url")] if (window or {}).get("source_url") else []
    sources=[x.get("source_url") for x in window if x.get("source_url")]; ok=any(x["start_month"]<=planting_date.month<=x["end_month"] for x in window)
    return ("PASS","planting date is inside verified planting window",sources) if ok else ("FAIL","planting date is outside verified planting windows",sources)

def _salinity_status(crop: dict[str, Any], ec: float | None) -> tuple[str, str]:
    if ec is None: return "UNKNOWN", "soil salinity EC is missing; salinity compatibility cannot be verified"
    match = re.search(r"<\s*(\d+(?:\.\d+)?)", str(crop.get("soil_characteristics", {}).get("salinity_optimal", "")))
    if not match: return "UNKNOWN", "crop salinity threshold is not structured in the catalog"
    limit = float(match.group(1))
    return ("FAIL", f"soil salinity EC {ec:g} dS/m meets or exceeds the sourced crop limit") if ec >= limit else ("PASS", "soil salinity EC is below the sourced crop limit")

def _water_status(crop: dict[str, Any], farm) -> tuple[str, str]:
    requirement = crop.get("water_requirement", {})
    if requirement.get("min_mm_season") is None: return "UNKNOWN", "seasonal crop-water requirement is unavailable"
    if farm.irrigation_available is False and farm.freshwater_availability == "limited": return "FAIL", "verified crop-water requirement exists but irrigation is unavailable and freshwater is limited"
    if farm.irrigation_available is True and farm.irrigation_water_ec is None: return "UNKNOWN", "irrigation-water EC is missing; water salinity compatibility cannot be verified"
    if farm.irrigation_available is None or farm.freshwater_availability == "unknown": return "UNKNOWN", "irrigation/freshwater availability is incomplete; rainfall is not irrigation demand"
    return "PASS", "water access is reported; crop demand still requires field water-balance verification"

def _strategy_rank(target: str, current: str, records: dict[str, Any], strategy: str, priority: str) -> tuple:
    crop = records[target]
    is_legume = bool(crop.get("legume", {}).get("is_legume"))
    water_max = crop.get("water_requirement", {}).get("max_mm_season")
    if strategy == "current_practice": base = (target != current, 0 if target == current else 1)
    elif strategy == "water_saving":
        sensitivity = crop.get("water_requirement", {}).get("drought_sensitivity", "unknown")
        sensitivity_rank = {"low": 0, "low-medium": 1, "medium": 2, "medium-high": 3, "high": 4, "unknown": 5}.get(sensitivity, 5)
        base = (sensitivity_rank, water_max if water_max is not None else float("inf"))
    else: base = (not is_legume, 0 if is_legume else 1)
    priority_bonus = {"water": 0 if strategy == "water_saving" else 1, "soil": 0 if strategy == "soil_recovery" else 1}.get(priority, 0)
    return (*base, priority_bonus, target)

def _matching_region(rules: dict[str, Any], latitude: float | None, longitude: float | None) -> dict[str, Any] | None:
    """Match only explicitly configured geographic coverage; never infer a region."""
    if latitude is None or longitude is None: return None
    regions=rules.get("regions") or []
    for region in regions:
        coverage=region.get("coverage",{})
        if coverage.get("type")=="point" and abs(latitude-coverage.get("latitude",999)) < 1e-6 and abs(longitude-coverage.get("longitude",999)) < 1e-6: return region
        if coverage.get("type")=="bbox" and coverage.get("min_lat") <= latitude <= coverage.get("max_lat") and coverage.get("min_lon") <= longitude <= coverage.get("max_lon"): return region
        polygon=coverage.get("polygon")
        if coverage.get("type")=="polygon" and isinstance(polygon,list) and _point_in_polygon(latitude,longitude,polygon): return region
    legacy=rules.get("applicability",{})
    for point in legacy.get("supported_locations",[]):
        if abs(latitude-point["latitude"]) < 1e-6 and abs(longitude-point["longitude"]) < 1e-6: return {"region_id":point.get("name","legacy"),"coverage":{"type":"point","latitude":point["latitude"],"longitude":point["longitude"]},"calendar":rules.get("planting_windows",{}),"transitions":rules.get("compatibility",[]),"source_urls":[],"valid_from":None,"valid_to":None}
    return None

def _point_in_polygon(latitude: float, longitude: float, polygon: list[list[float]]) -> bool:
    inside=False
    for index in range(len(polygon)):
        y1,x1=polygon[index-1]; y2,x2=polygon[index]
        if (x1>longitude)!=(x2>longitude) and latitude < (y2-y1)*(longitude-x1)/(x2-x1)+y1: inside=not inside
    return inside

def compare_rotation(scenario: RotationScenario)->RotationCompareResponse:
    records,rules,summary=_load(); location=None; availability={}; location_warnings=[]; daily_path=Path("__missing_location_dataset__"); summary={}
    if scenario.farm.latitude is not None:
        location={"latitude":scenario.farm.latitude,"longitude":scenario.farm.longitude}
        located=load_location(ROOT, scenario.farm.latitude, scenario.farm.longitude)
        availability,location_warnings,daily_path=located.availability,located.warnings,located.daily_path or Path("__missing_location_dataset__")
        summary=located.climate if isinstance(located.climate,dict) else {}
    candidates=scenario.candidate_crop_ids or list(records); current=scenario.farm.current_crop.strip().lower().replace(" ","_"); period=summary.get("period") or {}; daily_period=f"{period['start']}\u2013{period['end']}" if period.get("start") and period.get("end") else None; recommendations=[]; rejected=[]; missing=list(location_warnings)
    applicability_reason=None; region=_matching_region(rules,scenario.farm.latitude,scenario.farm.longitude); evaluation_rules=rules
    if scenario.farm.latitude is None:
        rules_applicable=False; applicability_reason="FarmProfile latitude and longitude are required for location-specific climate evaluation."; missing.append(applicability_reason)
    else:
        rules_applicable=region is not None
        if region:
            evaluation_rules={**rules,"planting_windows":region.get("calendar") or rules.get("planting_windows",{}),"compatibility":region.get("transitions") or rules.get("compatibility",[])}
        applicability_reason=None if rules_applicable else rules.get("applicability",{}).get("unsupported_reason")
        if applicability_reason: missing.append(applicability_reason)
    if current not in records:
        return RotationCompareResponse(recommendations=[], rejected_alternatives=[RejectedAlternative(crop_id=current, sequence=[current], eligibility="FAIL", reasons=["current crop is absent from verified catalog"], sources=[])], missing_data_warnings=["Current crop is unsupported; no rotation comparison is scientifically valid."], warnings=["NASA POWER is historical climate context, not a future forecast."], provenance=_provenance(summary,daily_period,location,availability,location_warnings,rules,applicability_reason), scoring=_scoring_metadata())
    candidates = sorted([target for target in candidates if target in records], key=lambda target: _strategy_rank(target, current, records, scenario.strategy, scenario.farm.farmer_priority)) + [target for target in candidates if target not in records]
    for target in candidates:
        if target not in records:
            rejected.append(RejectedAlternative(crop_id=target,sequence=[current,target],eligibility="FAIL",reasons=["crop is absent from verified catalog"],sources=[]));continue
        crop=records[target]; sources=list(crop.get("source_references",[])); transition,transition_reason,transition_sources=_transition(current,target,evaluation_rules,rules_applicable); sources+=transition_sources; calendar,calendar_reason,calendar_sources=_calendar(target,scenario.farm.planting_date,evaluation_rules,rules_applicable); sources+=calendar_sources; frame,window_reason=_window(scenario.farm.planting_date,crop.get("growth_duration",{}).get("max_days"),daily_path)
        temp=crop.get("temperature",{}); soil=crop.get("soil_ph",{}); warnings=[x for status,x in ((transition,transition_reason),(calendar,calendar_reason)) if status=="UNKNOWN"]; reasons=[transition_reason,calendar_reason]
        water_balance=None
        if frame is None: temperature_status="UNKNOWN"; temperature_reason=window_reason; rainfall_status="UNKNOWN"; rainfall_reason="growing-window precipitation unavailable or cannot be compared to annual reference"; missing += [f"{target}: {window_reason}"]
        else:
            temperature_status,temperature_reason=_range(float(frame.temperature_avg_c.mean()),temp.get("optimal",{}),temp.get("absolute",{}),"min_c","max_c"); rainfall_total=float(frame.precipitation_mm_day.sum()); rainfall_status="UNKNOWN"; rainfall_reason=f"growing-window precipitation is {rainfall_total:.2f} mm; catalog rainfall reference is annual and was not compared to this seasonal total"
            et0=reference_et0_fao56(frame,float(scenario.farm.latitude)); water_balance=crop_et_and_irrigation(et0,crop.get("fa056_crop_coefficient"),rainfall_total,effective_rainfall_scs(frame))
            water_balance["growing_period_rainfall_mm"]=rainfall_total
            water_balance["data_coverage"]={"start":frame.date.min().date().isoformat(),"end":frame.date.max().date().isoformat(),"observations":int(len(frame))}
            water_balance["seasonal_rainfall_mm"]=(summary.get("seasonal_metrics") or [])
            water_balance["monthly_rainfall_mm"]=(summary.get("monthly_metrics") or [])
            if water_balance["status"]=="PASS": rainfall_status="PASS"; rainfall_reason=f"growing-period rainfall {rainfall_total:.2f} mm; FAO-56 ETc {water_balance['etc_total_mm']:.2f} mm; estimated irrigation deficit {water_balance['irrigation_deficit_mm']:.2f} mm"
            else: rainfall_reason += "; " + water_balance.get("reason","FAO-56 water balance unavailable")
        # Annual ECOCROP rainfall is context only; it is never used as a hard check for a growth window.
        rainfall_reference=crop.get("rainfall",{}); annual_note=f"annual rainfall reference: {rainfall_reference.get('optimal',{}).get('min_mm_year')}-{rainfall_reference.get('optimal',{}).get('max_mm_year')} mm/year; context only"
        if scenario.farm.soil_ph is None: soil_status,soil_reason="UNKNOWN","soil pH is missing; SoilGrids has no values"
        else: soil_status,soil_reason=_range(scenario.farm.soil_ph,soil.get("optimal",{}),soil.get("absolute",{}),"min","max")
        water_status,water_reason=_water_status(crop,scenario.farm); salinity_status,salinity_reason=_salinity_status(crop,scenario.farm.soil_salinity_ec)
        # Rainfall-window evidence is an explicit suitability dimension. It is
        # currently UNKNOWN by policy because the catalog rainfall bounds are
        # annual context, not a verified seasonal threshold. It must therefore
        # participate in eligibility; otherwise an UNKNOWN climate dimension
        # could incorrectly produce PASS.
        statuses={transition,calendar,temperature_status,rainfall_status,soil_status,salinity_status,water_status}; hard="FAIL" if "FAIL" in statuses else "UNKNOWN" if "UNKNOWN" in statuses else "PASS"; eligibility=hard; score=None
        for status,reason in [(temperature_status,temperature_reason),(rainfall_status,rainfall_reason),(soil_status,soil_reason),(salinity_status,salinity_reason),(water_status,water_reason)]:
            if status=="UNKNOWN": warnings.append(reason); missing.append(f"{target}: {reason}")
        if scenario.strategy=="current_practice" and target==current:reasons.append("baseline continuation of current practice")
        elif scenario.strategy=="water_saving":reasons.append("water-saving ranking uses sourced water metadata only; no precise water saving is claimed")
        elif scenario.strategy=="soil_recovery":reasons.append("soil-recovery ranking recognizes sourced legume characteristics only; benefit is conditional")
        water_evidence=(f"Water evidence: ET0 {water_balance.get('et0_total_mm','UNKNOWN')} mm; ETc {water_balance.get('etc_total_mm','UNKNOWN')} mm; effective rainfall {water_balance.get('effective_rainfall_mm','UNKNOWN')} mm; irrigation deficit {water_balance.get('irrigation_deficit_mm','UNKNOWN')} mm; growing-period rainfall {water_balance.get('growing_period_rainfall_mm','UNKNOWN')} mm" if water_balance else "Water evidence: unavailable")
        rainfall_evidence=(f"Rainfall evidence: {len(water_balance.get('monthly_rainfall_mm',[]))} monthly and {len(water_balance.get('seasonal_rainfall_mm',[]))} seasonal records" if water_balance else "Rainfall evidence: unavailable")
        rationale=[water_evidence,rainfall_evidence]+reasons+[annual_note,temperature_reason,rainfall_reason,water_reason,soil_reason,salinity_reason]; duration=crop.get("growth_duration",{}).get("max_days")
        if all(x=="PASS" for x in statuses) and rainfall_status=="PASS": score=round(sum(x=="PASS" for x in statuses)/len(statuses)*100,2)
        climate_status="DATA_UNAVAILABLE" if frame is None and availability.get("climate") in {None,"unavailable"} else "FAIL" if temperature_status=="FAIL" else "NEEDS_INPUT" if "UNKNOWN" in {temperature_status,rainfall_status} or water_balance is None or (water_balance and water_balance.get("status")!="PASS") else "PASS"
        farm_missing=scenario.farm.missing_evidence(target); farm_missing += ([] if rules_applicable else ["verified regional calendar and rotation rules"])
        farm_status="FAIL" if "FAIL" in statuses else "DATA_UNAVAILABLE" if climate_status=="DATA_UNAVAILABLE" else "NEEDS_INPUT" if farm_missing or "UNKNOWN" in statuses else "PASS"
        climate_result=EvaluationResult(status=climate_status,reasons=[temperature_reason,rainfall_reason],missing_evidence=[window_reason] if frame is None else (["verified growing-period rainfall threshold"] if rainfall_status=="UNKNOWN" else []),calculations=water_balance or {},provenance=sorted(set(x for x in sources if x)))
        farm_result=EvaluationResult(status=farm_status,reasons=rationale,missing_evidence=sorted(set(farm_missing)),calculations={},provenance=sorted(set(x for x in sources if x)))
        final_decision="PASS" if climate_status=="PASS" and farm_status=="PASS" else "FAIL" if climate_status=="FAIL" or farm_status=="FAIL" else None
        item=RotationRecommendation(sequence=[current,target],crop_id=target,crop_name=crop["crop_name"],strategy=scenario.strategy,eligibility=eligibility,score=score,growth_duration_days=duration,hard_constraints_pass=hard,suitability={"temperature":temperature_status,"rainfall_window":rainfall_status,"water":water_status,"soil":soil_status,"salinity":salinity_status},rationale=rationale,warnings=sorted(set(warnings)),sources=sorted(set(x for x in sources if x)),water_balance=water_balance,climate_suitability=climate_result,farm_suitability=farm_result,final_decision=final_decision)
        (recommendations if eligibility!="FAIL" else rejected).append(item if eligibility!="FAIL" else RejectedAlternative(crop_id=target,sequence=[current,target],eligibility="FAIL",reasons=rationale,sources=item.sources))
    if not recommendations:missing.append("No eligible or assessable alternatives were returned.")
    return RotationCompareResponse(recommendations=recommendations,rejected_alternatives=rejected,missing_data_warnings=sorted(set(missing)),warnings=["NASA POWER is historical climate context, not a future forecast.","Precipitation is not evapotranspiration or irrigation demand.","UNKNOWN is not PASS; null scores are intentional when suitability cannot be calculated.",*location_warnings],provenance=_provenance(summary,daily_period,location,availability,location_warnings,rules,applicability_reason),scoring=_scoring_metadata())
