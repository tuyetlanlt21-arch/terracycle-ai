import pandas as pd
from datascience.rotation_engine import assess_climate_window, assess_sequence, load_knowledge_base, rank_strategy, validate_sequence

def climate(start="2024-11-01", end="2025-06-30"):
    dates=pd.date_range(start,end)
    return pd.DataFrame({"date":dates,"temperature_avg_c":25.0,"temperature_max_c":32.0,"precipitation_mm_day":2.0,"relative_humidity_pct":80.0,"solar_radiation_kwh_m2_day":4.0,"wind_speed_m_s":2.0})

def test_crop_specific_window_returns_unknown_for_annual_rainfall_basis():
    records,_=load_knowledge_base(); result=assess_climate_window(climate(),records["rice"],"2024-11-01")
    assert result["status"]=="PASS"; assert result["rainfall_status"]=="UNKNOWN"; assert result["rainfall_total_mm"] is not None

def test_sequence_rejects_overlap_and_unknown_crop():
    records,_=load_knowledge_base(); frame=climate()
    overlap=[{"crop_id":"rice","planting_date":"2024-11-01","duration_days":180},{"crop_id":"soybean","planting_date":"2025-01-01","duration_days":90}]
    result=assess_sequence(overlap,{"current_crop":"rice"},frame)
    assert result["status"]=="FAIL" and any("overlaps" in reason for reason in result["reasons"])
    invalid=validate_sequence([{"crop_id":"unknown","planting_date":"2024-11-01","duration_days":30}])
    assert invalid["status"]=="PASS"
    result=assess_sequence([{"crop_id":"unknown","planting_date":"2024-11-01","duration_days":30}],{"current_crop":"rice"},frame)
    assert result["status"]=="FAIL" and any("unsupported" in reason for reason in result["reasons"])

def test_sequence_checks_transition_and_missing_climate():
    frame=climate(); sequence=[{"crop_id":"rice","planting_date":"2024-11-01","duration_days":180},{"crop_id":"maize","planting_date":"2025-05-01","duration_days":65}]
    result=assess_sequence(sequence,{"current_crop":"rice"},frame)
    assert result["status"]=="FAIL" and any("transition" in reason for reason in result["reasons"])
    missing=assess_climate_window(frame.iloc[:10],load_knowledge_base()[0]["rice"],"2024-11-01")
    assert missing["status"]=="UNKNOWN"

def test_strategy_ranking_is_sourced_and_priority_does_not_override_feasibility():
    records,_=load_knowledge_base(); ids=["rice","soybean","mung_bean"]
    assert rank_strategy(ids,"current_practice","yield",records,"rice")[0]=="rice"
    assert rank_strategy(ids,"water_saving","water",records,"rice")[0]=="soybean"
    assert rank_strategy(ids,"soil_recovery","soil",records,"rice")[0] in {"mung_bean","soybean"}
