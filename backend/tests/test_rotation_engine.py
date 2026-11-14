from app.models import FarmProfile, RotationScenario
from app.services.decision import compare_rotation

def farm(**overrides):
    data={"current_crop":"rice","farm_area_ha":1,"soil_ph":6.0,"soil_salinity_ec":1.0,"irrigation_water_ec":0.5,"irrigation_available":True,"freshwater_availability":"adequate","farmer_priority":"yield","planning_month":11}; data.update(overrides); return FarmProfile.model_validate(data)

def test_valid_baseline_is_reproducible():
    scenario=RotationScenario(farm=farm(),strategy="current_practice",candidate_crop_ids=["rice"])
    first=compare_rotation(scenario); second=compare_rotation(scenario)
    assert first.recommendations[0].eligibility=="UNKNOWN"; assert first.recommendations[0].score is None; assert first.recommendations[0].score==second.recommendations[0].score; assert first.provenance["climate_period"]=="20200101–20251231"

def test_incompatible_transition_is_rejected():
    result=compare_rotation(RotationScenario(farm=farm(),strategy="current_practice",candidate_crop_ids=["maize"]))
    assert result.recommendations==[]; assert result.rejected_alternatives[0].eligibility=="FAIL"; assert "no supported transition" in " ".join(result.rejected_alternatives[0].reasons)

def test_missing_soil_and_soilgrids_stay_unknown():
    result=compare_rotation(RotationScenario(farm=farm(soil_ph=None,soil_salinity_ec=None),strategy="soil_recovery",candidate_crop_ids=["rice"]))
    item=result.recommendations[0]; assert item.eligibility=="UNKNOWN"; assert item.score is None; assert result.provenance["soil_status"]=="no_values"

def test_unknown_calendar_and_missing_mung_water_are_not_pass():
    result=compare_rotation(RotationScenario(farm=farm(),strategy="water_saving",candidate_crop_ids=["rice","mung_bean"]))
    mung=next(x for x in result.recommendations if x.crop_id=="mung_bean"); assert mung.eligibility=="UNKNOWN"; assert any("water" in warning for warning in mung.warnings)

def test_no_eligible_alternatives_is_explicit():
    result=compare_rotation(RotationScenario(farm=farm(),strategy="current_practice",candidate_crop_ids=["maize"]))
    assert not result.recommendations; assert any("No eligible" in warning for warning in result.missing_data_warnings)

def test_annual_rainfall_is_not_applied_to_seasonal_mung_window():
    scenario=RotationScenario(farm=farm(planting_date="2025-01-01"),strategy="water_saving",candidate_crop_ids=["mung_bean"])
    result=compare_rotation(scenario); item=result.recommendations[0]
    assert item.eligibility=="UNKNOWN"; assert item.suitability["rainfall_window"]=="UNKNOWN"; assert not any("outside the absolute range" in x for x in item.rationale)

def test_missing_planting_date_keeps_time_suitability_unknown():
    result=compare_rotation(RotationScenario(farm=farm(planting_date=None),strategy="current_practice",candidate_crop_ids=["rice"]))
    item=result.recommendations[0]; assert item.eligibility=="UNKNOWN"; assert any("planting_date is missing" in x for x in item.warnings)

def test_window_uses_daily_precipitation_and_growth_duration():
    result=compare_rotation(RotationScenario(farm=farm(planting_date="2024-11-01"),strategy="current_practice",candidate_crop_ids=["rice"]))
    item=result.recommendations[0]; assert "growing-window precipitation is" in " ".join(item.rationale); assert item.growth_duration_days==180; assert item.suitability["rainfall_window"]=="UNKNOWN"

def test_high_salinity_is_hard_failure_and_freshwater_shortage_is_not_pass():
    result=compare_rotation(RotationScenario(farm=farm(soil_salinity_ec=4.0, irrigation_available=False, freshwater_availability="limited"),strategy="water_saving",candidate_crop_ids=["rice"]))
    assert result.recommendations == []
    assert result.rejected_alternatives[0].eligibility == "FAIL"
    assert any("salinity" in reason.lower() for reason in result.rejected_alternatives[0].reasons)

def test_unsupported_current_crop_is_rejected():
    result=compare_rotation(RotationScenario(farm=farm(current_crop="cassava"),strategy="current_practice",candidate_crop_ids=["rice"]))
    assert result.recommendations == []
    assert result.rejected_alternatives[0].eligibility == "FAIL"

def test_strategy_order_changes_with_supported_evidence_and_priority():
    candidates=["rice","soybean","mung_bean"]
    farm_profile=farm(planting_date="2024-11-01", farmer_priority="water")
    current=compare_rotation(RotationScenario(farm=farm_profile,strategy="current_practice",candidate_crop_ids=candidates))
    water=compare_rotation(RotationScenario(farm=farm_profile,strategy="water_saving",candidate_crop_ids=candidates))
    recovery=compare_rotation(RotationScenario(farm=farm_profile,strategy="soil_recovery",candidate_crop_ids=candidates))
    assert current.recommendations[0].crop_id == "rice"
    assert water.recommendations[0].crop_id == "soybean"
    assert recovery.recommendations[0].crop_id in {"mung_bean", "soybean"}
    assert all("water-saving" in " ".join(item.rationale) for item in water.recommendations)

def test_fully_evidenced_constraints_still_expose_unverified_rainfall_basis():
    result=compare_rotation(RotationScenario(farm=farm(planting_date="2024-11-01"),strategy="current_practice",candidate_crop_ids=["rice"]))
    item=result.recommendations[0]
    assert item.suitability["temperature"] == "PASS"
    assert item.suitability["soil"] == "PASS"
    assert item.suitability["salinity"] == "PASS"
    assert item.suitability["rainfall_window"] == "UNKNOWN"
    assert item.score is None

def test_deterministic_end_to_end_scenarios():
    scenarios=[
        (farm(planting_date="2024-11-01"), "current_practice", ["rice"]),
        (farm(planting_date="2024-11-01",farmer_priority="water"), "water_saving", ["rice","soybean"]),
        (farm(planting_date="2024-11-01",farmer_priority="soil"), "soil_recovery", ["rice","mung_bean","soybean"]),
        (farm(planting_date="2025-06-01",irrigation_available=False,freshwater_availability="limited"), "water_saving", ["rice","soybean"]),
        (farm(planting_date="2024-11-01",soil_ph=None,soil_salinity_ec=None), "soil_recovery", ["rice","soybean"]),
    ]
    for profile,strategy,candidates in scenarios:
        result=compare_rotation(RotationScenario(farm=profile,strategy=strategy,candidate_crop_ids=candidates))
        assert result.provenance["climate_source"] == "NASA POWER"
        assert result.provenance["forecast_available"] is False
        assert result.recommendations or result.rejected_alternatives
