import pandas as pd
import pytest
from datascience.salt_risk import STAGES, assess, assess_row

def row(**changes):
    base = {"date":"2025-01-01", "precipitation_power_mm_day":0.0, "precipitation_imerg_mm_day":0.0, "precipitation_gldas_mm_day":0.0, "temperature_avg_c":26, "relative_humidity_pct":70, "solar_radiation_kwh_m2_day":18, "evapotranspiration_gldas_mm_day":3}
    base.update(changes); return pd.Series(base)

def test_low_and_critical_levels_are_reproducible():
    assert assess_row(row(), "preparation")["risk_level"] == "LOW"
    result = assess_row(row(precipitation_imerg_mm_day=12, relative_humidity_pct=90, solar_radiation_kwh_m2_day=8, evapotranspiration_gldas_mm_day=1), "crystallization")
    assert result["risk_level"] == "CRITICAL" and result["risk_score"] >= 75

def test_all_stages_are_supported():
    assert {assess_row(row(), stage)["production_stage"] for stage in STAGES} == set(STAGES)

def test_missing_data_is_insufficient_not_low():
    result = assess_row(row(precipitation_imerg_mm_day=float("nan")), "evaporation")
    assert result["status"] == "INSUFFICIENT_DATA" and result["risk_level"] is None

def test_boundary_and_separate_rain_sources():
    result = assess_row(row(precipitation_power_mm_day=1.0, precipitation_imerg_mm_day=0, precipitation_gldas_mm_day=0), "evaporation")
    assert result["component_scores"]["rain_exposure"] == 50
    assert result["contributing_factors"][0].startswith("Highest source rainfall: POWER")

def test_invalid_values_fail():
    with pytest.raises(ValueError): assess_row(row(precipitation_gldas_mm_day=-1), "harvesting")

def test_assessment_report_and_salinity_disclaimer():
    result, report = assess(pd.DataFrame([row()]), "harvesting", brine_salinity=20)
    assert report["assessment_type"] == "historical" and bool(result.loc[0, "salinity_used"]) is False
    assert result.loc[0, "data_confidence"] == 85
    assert result.loc[0, "data_confidence_type"] == "MVP_DATA_QUALITY_SCORE_NOT_PROBABILITY"
    assert "not probability" in report["configuration"]["data_confidence_semantics"]
