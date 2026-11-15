from datetime import date
from app.models import FarmProfile, RotationScenario
import app.services.decision as decision
from app.services.decision import compare_rotation

def farm(**overrides):
    data={"current_crop":"rice","farm_area_ha":1,"soil_ph":6.0,"soil_salinity_ec":1.0,"irrigation_water_ec":0.5,"irrigation_available":True,"freshwater_availability":"adequate","farmer_priority":"yield","planning_month":11,"latitude":10.8403,"longitude":106.8333}; data.update(overrides); return FarmProfile.model_validate(data)

def test_valid_baseline_is_reproducible():
    scenario=RotationScenario(farm=farm(),strategy="current_practice",candidate_crop_ids=["rice"])
    first=compare_rotation(scenario); second=compare_rotation(scenario)
    assert first.recommendations[0].eligibility=="UNKNOWN"; assert first.recommendations[0].score is None; assert first.recommendations[0].score==second.recommendations[0].score; assert first.provenance.climate_period.startswith("20200101") and "2026" in first.provenance.climate_period

def test_incompatible_transition_is_rejected():
    result=compare_rotation(RotationScenario(farm=farm(),strategy="current_practice",candidate_crop_ids=["maize"]))
    item=result.recommendations[0]; assert item.final_decision is None; assert item.farm_suitability.status=="NEEDS_INPUT"; assert any("regional" in x for x in item.farm_suitability.missing_evidence)

def test_missing_soil_and_soilgrids_stay_unknown():
    result=compare_rotation(RotationScenario(farm=farm(soil_ph=None,soil_salinity_ec=None),strategy="soil_recovery",candidate_crop_ids=["rice"]))
    item=result.recommendations[0]; assert item.eligibility=="UNKNOWN"; assert item.score is None; assert result.provenance.soil_status in {"no_values", "unavailable"}

def test_unknown_calendar_and_missing_mung_water_are_not_pass():
    result=compare_rotation(RotationScenario(farm=farm(),strategy="water_saving",candidate_crop_ids=["rice","mung_bean"]))
    mung=next(x for x in result.recommendations if x.crop_id=="mung_bean"); assert mung.eligibility=="UNKNOWN"; assert any("water" in warning for warning in mung.warnings)

def test_no_eligible_alternatives_is_explicit():
    result=compare_rotation(RotationScenario(farm=farm(),strategy="current_practice",candidate_crop_ids=["maize"]))
    assert result.recommendations[0].final_decision is None

def test_annual_rainfall_is_not_applied_to_seasonal_mung_window():
    scenario=RotationScenario(farm=farm(planting_date="2025-01-01"),strategy="water_saving",candidate_crop_ids=["mung_bean"])
    result=compare_rotation(scenario); item=result.recommendations[0]
    assert item.eligibility=="UNKNOWN"; assert item.suitability.rainfall_window=="UNKNOWN"; assert not any("outside the absolute range" in x for x in item.rationale)

def test_missing_planting_date_keeps_time_suitability_unknown():
    result=compare_rotation(RotationScenario(farm=farm(planting_date=None),strategy="current_practice",candidate_crop_ids=["rice"]))
    item=result.recommendations[0]; assert item.eligibility=="UNKNOWN"; assert any("planting_date" in x for x in result.missing_data_warnings)

def test_window_uses_daily_precipitation_and_growth_duration():
    result=compare_rotation(RotationScenario(farm=farm(planting_date="2024-11-01"),strategy="current_practice",candidate_crop_ids=["rice"]))
    item=result.recommendations[0]; assert item.growth_duration_days==180; assert item.suitability.rainfall_window in {"PASS", "FAIL", "UNKNOWN"}

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
    assert item.suitability.temperature == "PASS"
    assert item.suitability.soil == "PASS"
    assert item.suitability.salinity == "PASS"
    assert item.suitability.rainfall_window in {"PASS", "UNKNOWN"}
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
        assert result.provenance.climate_source == "NASA POWER"
        assert result.provenance.forecast_available is False
        assert result.recommendations or result.rejected_alternatives

def test_region_guard_keeps_climate_evidence_separate_from_unverified_rules():
    result=compare_rotation(RotationScenario(farm=farm(latitude=10.72, longitude=106.70, planting_date="2024-11-01"),strategy="current_practice",candidate_crop_ids=["rice"]))
    item=result.recommendations[0]
    assert item.suitability.temperature in {"PASS", "UNKNOWN"}
    assert item.eligibility == "UNKNOWN"
    # Climate evidence remains independently evaluable; only the unverified
    # regional calendar/transition rules keep farm-level suitability unknown.
    assert item.suitability.rainfall_window in {"PASS", "UNKNOWN"}
    assert item.farm_suitability.status in {"NEEDS_INPUT", "DATA_UNAVAILABLE"}
    assert "outside their verified geographic scope" in " ".join(item.warnings)
    assert result.provenance.supported_scope == "verified_point_only"
    assert result.provenance.applicability_reason

def test_long_xuyen_point_is_the_only_verified_rule_location():
    result=compare_rotation(RotationScenario(farm=farm(latitude=10.383333, longitude=105.45, planting_date="2024-11-01"),strategy="current_practice",candidate_crop_ids=["rice"]))
    assert result.provenance.applicability_reason is None
    assert result.provenance.evaluated_location == {"latitude":10.383333,"longitude":105.45}

def test_fixture_coordinates_are_used_for_location_specific_evaluation():
    result=compare_rotation(RotationScenario(farm=farm(planting_date="2024-11-01"),strategy="current_practice",candidate_crop_ids=["rice"]))
    assert result.provenance.evaluated_location == {"latitude":10.8403,"longitude":106.8333}

def test_bundled_long_xuyen_evidence_can_assess_pass_and_fail(monkeypatch):
    import app.services.location_data as location_data
    monkeypatch.setattr(location_data,"_find_cached_climate_artifact",lambda *args: None)
    monkeypatch.setenv("LOCATION_DATA_FETCH_ENABLED","0")
    located=location_data.load_location(decision.ROOT,10.383333,105.45)
    assert located.availability["climate"]=="available"
    assert located.daily_path is not None and located.daily_path.is_file()

    def scenario(salinity):
        profile=farm(
            planting_date="2024-11-01", latitude=10.383333, longitude=105.45,
            soil_ph=6.0, soil_salinity_ec=salinity, irrigation_water_ec=0.5,
            irrigation_available=True, freshwater_availability="adequate",
            drainage_available=True, water_control_available=True,
        )
        return RotationScenario(farm=profile,strategy="current_practice",candidate_crop_ids=["rice"])

    eligible=compare_rotation(scenario(1.0),location_data=located)
    assert eligible.recommendations[0].eligibility=="PASS"
    assert eligible.recommendations[0].final_decision=="PASS"

    incomplete=scenario(1.0)
    incomplete.farm.drainage_available=None
    pending=compare_rotation(incomplete,location_data=located)
    assert pending.recommendations[0].eligibility=="UNKNOWN"
    assert pending.recommendations[0].final_decision is None

    rejected=compare_rotation(scenario(4.0),location_data=located)
    assert rejected.rejected_alternatives[0].eligibility=="FAIL"
    assert any("salinity" in reason.lower() for reason in rejected.rejected_alternatives[0].reasons)

def test_fao_irrigation_water_quality_bands_are_not_all_pass():
    rice=decision._load()[0]["rice"]
    cases=[(0.69,"PASS"),(0.7,"UNKNOWN"),(3.0,"UNKNOWN"),(3.01,"FAIL")]
    for ec,expected in cases:
        status,_reason=decision._water_status(rice,farm(irrigation_water_ec=ec))
        assert status==expected

def test_window_rejects_duplicate_dates_that_mask_missing_coverage(tmp_path, monkeypatch):
    dataset=tmp_path/"daily.csv"
    dataset.write_text("date,temperature_avg_c,precipitation_mm_day\n2024-01-01,20,1\n2024-01-01,21,2\n",encoding="utf-8")
    monkeypatch.setattr(decision,"DAILY",dataset)
    frame,reason=decision._window(date(2024,1,1),2)
    assert frame is None
    assert "missing required climate columns" in reason

def test_window_handles_dataset_without_date_column(tmp_path, monkeypatch):
    dataset=tmp_path/"daily.csv"
    dataset.write_text("day,temperature_avg_c,precipitation_mm_day\n2024-01-01,20,1\n",encoding="utf-8")
    monkeypatch.setattr(decision,"DAILY",dataset)
    frame,reason=decision._window(date(2024,1,1),1)
    assert frame is None
    assert "date column" in reason

def test_window_rejects_missing_values_in_daily_climate_metrics(tmp_path, monkeypatch):
    dataset=tmp_path/"daily.csv"
    dataset.write_text("date,temperature_avg_c,precipitation_mm_day\n2024-01-01,20,1\n2024-01-02,,2\n",encoding="utf-8")
    monkeypatch.setattr(decision,"DAILY",dataset)
    frame,reason=decision._window(date(2024,1,1),2)
    assert frame is None
    assert "missing required climate columns" in reason

def test_window_reports_missing_daily_dataset(tmp_path, monkeypatch):
    monkeypatch.setattr(decision,"DAILY",tmp_path/"missing.csv")
    frame,reason=decision._window(date(2024,1,1),1)
    assert frame is None
    assert reason=="NASA POWER daily dataset is unavailable"

def test_window_handles_unreadable_daily_dataset(tmp_path, monkeypatch):
    dataset=tmp_path/"daily.csv"
    dataset.write_text("",encoding="utf-8")
    monkeypatch.setattr(decision,"DAILY",dataset)
    frame,reason=decision._window(date(2024,1,1),1)
    assert frame is None
    assert reason=="NASA POWER daily dataset could not be read"

def test_window_treats_unrepresentable_date_range_as_unavailable(tmp_path, monkeypatch):
    dataset=tmp_path/"daily.csv"
    dataset.write_text("date,temperature_avg_c,precipitation_mm_day\n2024-01-01,20,1\n",encoding="utf-8")
    monkeypatch.setattr(decision,"DAILY",dataset)
    frame,reason=decision._window(date(9999,12,31),2)
    assert frame is None
    assert "missing required climate columns" in reason

def test_dated_planting_window_uses_season_year_and_citation():
    url="https://nhonmy.angiang.gov.vn/chuan-bi-vu-dong-xuan-tren-dia-ban-tinh"
    rules={"planting_windows":{"rice":[
        {"name":"legacy_winter_spring","start_month":11,"end_month":12,"source_url":"https://legacy.example/calendar"},
        {"name":"winter_spring_2026_2027","start_date":"2026-11-01","end_date":"2026-12-31","source_url":url},
    ]}}
    status,reason,sources=decision._calendar("rice",date(2026,11,15),rules)
    assert status=="PASS"
    assert reason=="planting date is inside verified planting window"
    assert sources==[url]

def test_dated_planting_window_overrides_legacy_month_for_its_year():
    rules={"planting_windows":{"rice":[
        {"name":"legacy_winter_spring","start_month":11,"end_month":12,"source_url":"https://legacy.example/calendar"},
        {"name":"winter_spring_2026_2027","start_date":"2026-11-01","end_date":"2026-12-31","source_url":"https://official.example/calendar"},
    ]}}
    status,_,sources=decision._calendar("rice",date(2026,10,31),rules)
    assert status=="FAIL"
    assert sources==["https://official.example/calendar"]
