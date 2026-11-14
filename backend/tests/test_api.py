import json
import logging
from fastapi.testclient import TestClient
import pytest
import app.main as main
import app.services.decision as decision
from app.main import app
client=TestClient(app)
def test_health_and_contract():
    assert client.get("/health").json()["status"]=="ok"
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"unknown","farm_area_ha":1},"strategy":"water_saving","candidate_crop_ids":["crop-unknown"]})
    body=response.json(); assert response.status_code==200; assert body["provenance"]["forecast_available"] is False; assert {"recommendations","rejected_alternatives","missing_data_warnings","provenance","scoring"}.issubset(body)
def test_new_endpoints():
    assert client.get("/api/crops").status_code==200; assert client.get("/api/soil/profile").status_code==200

def test_whitespace_only_current_crop_is_rejected():
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"   ","farm_area_ha":1},"strategy":"current_practice"})
    assert response.status_code==422

@pytest.mark.parametrize("field", ["soil_salinity_ec", "irrigation_water_ec"])
@pytest.mark.parametrize("value", [float("inf"), float("nan")])
def test_non_finite_farm_measurements_are_rejected(field, value):
    payload={"farm":{"current_crop":"rice","farm_area_ha":1,field:value},"strategy":"current_practice"}
    response=client.post("/api/rotations/compare",content=json.dumps(payload),headers={"Content-Type":"application/json"})
    assert response.status_code==422
    assert "input" not in response.json()["detail"][0]

@pytest.mark.parametrize(("farm", "missing_field"), [
    ({"farm_area_ha":1}, "current_crop"),
    ({"current_crop":"rice"}, "farm_area_ha"),
    ({"current_crop":None,"farm_area_ha":1}, "current_crop"),
    ({"current_crop":"rice","farm_area_ha":None}, "farm_area_ha"),
])
def test_required_farm_fields_return_structured_validation_errors(farm, missing_field):
    response=client.post("/api/rotations/compare",json={"farm":farm,"strategy":"current_practice"})
    assert response.status_code==422
    assert response.json()["detail"][0]["loc"]==["body","farm",missing_field]

@pytest.mark.parametrize("area", [0, 100001])
def test_farm_area_outside_supported_range_returns_422(area):
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":area},"strategy":"current_practice"})
    assert response.status_code==422

@pytest.mark.parametrize(("soil_ph", "expected_status"), [
    (3.49, 422),
    (3.5, 200),
    (9.0, 200),
    (9.01, 422),
])
def test_soil_ph_limits_match_frontend_form(soil_ph, expected_status):
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1,"soil_ph":soil_ph},"strategy":"current_practice","candidate_crop_ids":["rice"]})
    assert response.status_code==expected_status

@pytest.mark.parametrize(("location", "value"), [
    (("strategy",), "rotate_fast"),
    (("farm", "farmer_priority"), "profit"),
    (("farm", "freshwater_availability"), "plentiful"),
])
def test_unsupported_enums_return_structured_validation_errors(location, value):
    payload={"farm":{"current_crop":"rice","farm_area_ha":1},"strategy":"current_practice"}
    target=payload
    for key in location[:-1]:
        target=target[key]
    target[location[-1]]=value
    response=client.post("/api/rotations/compare",json=payload)
    assert response.status_code==422
    assert response.json()["detail"][0]["loc"]==["body",*location]

def test_invalid_calendar_date_returns_422():
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1,"planting_date":"2025-02-30"},"strategy":"current_practice"})
    assert response.status_code==422
    assert response.json()["detail"][0]["loc"]==["body","farm","planting_date"]

def test_null_measurements_remain_unknown():
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1,"soil_ph":None,"soil_salinity_ec":None,"irrigation_water_ec":None,"irrigation_available":None},"strategy":"current_practice","candidate_crop_ids":["rice"]})
    assert response.status_code==200
    item=response.json()["recommendations"][0]
    assert item["suitability"]["soil"]=="UNKNOWN"
    assert item["suitability"]["salinity"]=="UNKNOWN"
    assert item["suitability"]["water"]=="UNKNOWN"

@pytest.mark.parametrize("strategy", ["current_practice", "water_saving", "soil_recovery"])
def test_compare_response_has_consistent_recommendation_contract_for_each_strategy(strategy):
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1},"strategy":strategy,"candidate_crop_ids":["rice"]})
    assert response.status_code==200
    body=response.json()
    assert set(body)=={"recommendations","rejected_alternatives","missing_data_warnings","warnings","provenance","scoring"}
    item=body["recommendations"][0]
    assert set(item)=={"sequence","crop_id","crop_name","strategy","eligibility","score","growth_duration_days","hard_constraints_pass","suitability","rationale","warnings","sources"}
    assert item["strategy"]==strategy
    assert item["eligibility"] in {"PASS","FAIL","UNKNOWN"}
    assert item["score"] is None
    assert item["hard_constraints_pass"] in {"PASS","FAIL","UNKNOWN"}
    assert set(item["suitability"].values())<={"PASS","FAIL","UNKNOWN"}
    assert isinstance(item["rationale"],list)
    assert body["provenance"]["forecast_available"] is False

def test_compare_response_is_complete_when_no_candidate_is_eligible():
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1},"strategy":"water_saving","candidate_crop_ids":["unsupported-crop"]})
    assert response.status_code==200
    body=response.json()
    assert body["recommendations"]==[]
    rejected=body["rejected_alternatives"][0]
    assert set(rejected)=={"crop_id","sequence","eligibility","reasons","sources"}
    assert rejected["crop_id"]=="unsupported-crop"
    assert rejected["sequence"]==["rice","unsupported-crop"]
    assert rejected["eligibility"]=="FAIL"
    assert rejected["reasons"] and isinstance(rejected["reasons"],list)
    assert isinstance(rejected["sources"],list)
    assert body["missing_data_warnings"]
    assert body["warnings"]
    assert body["provenance"]["forecast_available"] is False
    assert body["scoring"]["weights"]

def test_provenance_and_scoring_schemas_are_consistent_for_supported_and_unsupported_crops():
    valid=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1},"strategy":"current_practice","candidate_crop_ids":["rice"]}).json()
    unsupported=client.post("/api/rotations/compare",json={"farm":{"current_crop":"unknown-crop","farm_area_ha":1},"strategy":"current_practice"}).json()
    expected_provenance={"climate_source","climate_period","climate_source_url","soil_status","forecast_available"}
    expected_scoring={"weights","score_definition","threshold_time_basis","annual_rainfall_policy","window_rainfall_policy"}
    assert set(valid["provenance"])==expected_provenance
    assert set(unsupported["provenance"])==expected_provenance
    assert set(valid["scoring"])==expected_scoring
    assert set(unsupported["scoring"])==expected_scoring

def test_climate_summary_uses_placeholder_when_processed_dataset_is_missing(tmp_path, monkeypatch):
    fallback=tmp_path/"shared/fixtures/climate-placeholder.json"
    fallback.parent.mkdir(parents=True)
    fallback.write_text('{"status":"PLACEHOLDER - NO MEASURED DATA","monthly":[]}',encoding="utf-8")
    monkeypatch.setattr(main,"ROOT",tmp_path)
    response=client.get("/api/climate/summary")
    assert response.status_code==200
    assert response.json()["status"]=="PLACEHOLDER - NO MEASURED DATA"

def test_corrupt_climate_summary_returns_data_unavailable_status(tmp_path, monkeypatch):
    summary=tmp_path/"data/processed/power/climate_summary.json"
    summary.parent.mkdir(parents=True)
    summary.write_text("{not-json",encoding="utf-8")
    monkeypatch.setattr(main,"ROOT",tmp_path)
    response=client.get("/api/climate/summary")
    assert response.status_code==503
    assert response.json()=={"detail":"Climate summary data is unavailable."}

def test_rotation_comparison_uses_placeholder_when_summary_file_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(decision,"CLIMATE",tmp_path/"missing-climate-summary.json")
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1},"strategy":"current_practice","candidate_crop_ids":["rice"]})
    assert response.status_code==200
    body=response.json()
    assert body["provenance"]["climate_period"] is None
    assert body["provenance"]["climate_source_url"] is None
    assert body["recommendations"][0]["suitability"]["temperature"]=="UNKNOWN"

def test_rotation_comparison_returns_503_for_corrupt_climate_summary(tmp_path, monkeypatch):
    summary=tmp_path/"climate_summary.json"
    summary.write_text("{not-json",encoding="utf-8")
    monkeypatch.setattr(decision,"CLIMATE",summary)
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1},"strategy":"current_practice"})
    assert response.status_code==503
    assert response.json()=={"detail":"Climate summary data is unavailable."}

def test_unexpected_server_error_is_generic_and_logged(monkeypatch, caplog):
    def fail_comparison(request):
        raise RuntimeError("private implementation detail")
    monkeypatch.setattr(main,"compare_rotation",fail_comparison)
    safe_client=TestClient(app,raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR):
        response=safe_client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1},"strategy":"current_practice"})
    assert response.status_code==500
    assert response.json()=={"detail":"Internal server error."}
    assert "private implementation detail" not in response.text
    assert "Unhandled backend error" in caplog.text

def test_corrupt_crop_catalog_is_reported_as_data_unavailable(tmp_path, monkeypatch):
    catalog=tmp_path/"data/reference/crop_catalog.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_text("{not-json",encoding="utf-8")
    monkeypatch.setattr(main,"ROOT",tmp_path)
    safe_client=TestClient(app,raise_server_exceptions=False)
    response=safe_client.get("/api/crops")
    assert response.status_code==503
    assert response.json()=={"detail":"Reference data is unavailable."}

def test_corrupt_rotation_rules_are_reported_as_data_unavailable(tmp_path, monkeypatch):
    rules=tmp_path/"rotation_rules.json"
    rules.write_text("{not-json",encoding="utf-8")
    monkeypatch.setattr(decision,"RULES",rules)
    safe_client=TestClient(app,raise_server_exceptions=False)
    response=safe_client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1},"strategy":"current_practice"})
    assert response.status_code==503
    assert response.json()=={"detail":"Reference data is unavailable."}

def test_missing_daily_climate_file_leaves_suitability_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(decision,"DAILY",tmp_path/"missing-daily.csv")
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1,"planting_date":"2024-11-01"},"strategy":"current_practice","candidate_crop_ids":["rice"]})
    assert response.status_code==200
    item=response.json()["recommendations"][0]
    assert item["eligibility"]=="UNKNOWN"
    assert item["suitability"]["temperature"]=="UNKNOWN"
    assert any("daily dataset is unavailable" in warning for warning in response.json()["missing_data_warnings"])

def test_crop_catalog_with_missing_required_record_field_is_data_error(tmp_path, monkeypatch):
    records=[{"crop_id":crop_id,"crop_name":crop_id} for crop_id in ("rice","maize","mung_bean","soybean")]
    del records[0]["crop_name"]
    catalog=tmp_path/"crop_catalog.json"
    catalog.write_text(json.dumps({"records":records}),encoding="utf-8")
    monkeypatch.setattr(decision,"CATALOG",catalog)
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1},"strategy":"current_practice"})
    assert response.status_code==503
    assert response.json()=={"detail":"Reference data is unavailable."}

def test_rotation_rules_with_invalid_collections_are_data_error(tmp_path, monkeypatch):
    rules=tmp_path/"rotation_rules.json"
    rules.write_text(json.dumps({"compatibility":"not-a-list","planting_windows":{}}),encoding="utf-8")
    monkeypatch.setattr(decision,"RULES",rules)
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1},"strategy":"current_practice"})
    assert response.status_code==503
    assert response.json()=={"detail":"Reference data is unavailable."}

def test_climate_summary_with_invalid_period_shape_is_data_error(tmp_path, monkeypatch):
    summary=tmp_path/"climate_summary.json"
    summary.write_text(json.dumps({"period":"not-an-object"}),encoding="utf-8")
    monkeypatch.setattr(decision,"CLIMATE",summary)
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1},"strategy":"current_practice"})
    assert response.status_code==503
    assert response.json()=={"detail":"Climate summary data is unavailable."}

def test_crop_endpoint_rejects_records_with_invalid_shape(tmp_path, monkeypatch):
    catalog=tmp_path/"data/reference/crop_catalog.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_text(json.dumps({"records":[{"crop_id":"rice"}]}),encoding="utf-8")
    monkeypatch.setattr(main,"ROOT",tmp_path)
    response=client.get("/api/crops")
    assert response.status_code==503
    assert response.json()=={"detail":"Reference data is unavailable."}

@pytest.mark.parametrize("malformed_value", ["long", []])
def test_crop_catalog_invalid_growth_duration_is_data_error(tmp_path, monkeypatch, malformed_value):
    catalog=json.loads(decision.CATALOG.read_text(encoding="utf-8"))
    catalog["records"][0]["growth_duration"]["max_days"]=malformed_value
    path=tmp_path/"crop_catalog.json"
    path.write_text(json.dumps(catalog),encoding="utf-8")
    monkeypatch.setattr(decision,"CATALOG",path)
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1,"planting_date":"2024-11-01"},"strategy":"current_practice","candidate_crop_ids":["rice"]})
    assert response.status_code==503
    assert response.json()=={"detail":"Reference data is unavailable."}

def test_crop_catalog_source_references_must_be_strings(tmp_path, monkeypatch):
    catalog=json.loads(decision.CATALOG.read_text(encoding="utf-8"))
    catalog["records"][0]["source_references"].append(42)
    path=tmp_path/"crop_catalog.json"
    path.write_text(json.dumps(catalog),encoding="utf-8")
    monkeypatch.setattr(decision,"CATALOG",path)
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1},"strategy":"current_practice"})
    assert response.status_code==503
    assert response.json()=={"detail":"Reference data is unavailable."}

def test_rotation_rule_source_urls_must_be_strings(tmp_path, monkeypatch):
    rules=json.loads(decision.RULES.read_text(encoding="utf-8"))
    rules["compatibility"][0]["source_urls"].append(42)
    path=tmp_path/"rotation_rules.json"
    path.write_text(json.dumps(rules),encoding="utf-8")
    monkeypatch.setattr(decision,"RULES",path)
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1},"strategy":"current_practice"})
    assert response.status_code==503
    assert response.json()=={"detail":"Reference data is unavailable."}

def test_rotation_rule_planting_window_source_url_must_be_string(tmp_path, monkeypatch):
    rules=json.loads(decision.RULES.read_text(encoding="utf-8"))
    rules["planting_windows"]["rice"][0]["source_url"]=42
    path=tmp_path/"rotation_rules.json"
    path.write_text(json.dumps(rules),encoding="utf-8")
    monkeypatch.setattr(decision,"RULES",path)
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1,"planting_date":"2024-11-01"},"strategy":"current_practice","candidate_crop_ids":["rice"]})
    assert response.status_code==503
    assert response.json()=={"detail":"Reference data is unavailable."}

def test_invalid_utf8_reference_file_is_reported_as_data_error(tmp_path, monkeypatch):
    catalog=tmp_path/"data/reference/crop_catalog.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_bytes(bytes([255]))
    monkeypatch.setattr(main,"ROOT",tmp_path)
    safe_client=TestClient(app,raise_server_exceptions=False)
    response=safe_client.get("/api/crops")
    assert response.status_code==503
    assert response.json()=={"detail":"Reference data is unavailable."}

def test_crop_catalog_invalid_drought_sensitivity_is_data_error(tmp_path, monkeypatch):
    catalog=json.loads(decision.CATALOG.read_text(encoding="utf-8"))
    catalog["records"][0]["water_requirement"]["drought_sensitivity"]=[]
    path=tmp_path/"crop_catalog.json"
    path.write_text(json.dumps(catalog),encoding="utf-8")
    monkeypatch.setattr(decision,"CATALOG",path)
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1},"strategy":"water_saving","candidate_crop_ids":["rice"]})
    assert response.status_code==503
    assert response.json()=={"detail":"Reference data is unavailable."}

def test_crop_catalog_invalid_water_requirement_is_data_error(tmp_path, monkeypatch):
    catalog=json.loads(decision.CATALOG.read_text(encoding="utf-8"))
    catalog["records"][0]["water_requirement"]["max_mm_season"]="high"
    path=tmp_path/"crop_catalog.json"
    path.write_text(json.dumps(catalog),encoding="utf-8")
    monkeypatch.setattr(decision,"CATALOG",path)
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1},"strategy":"water_saving","candidate_crop_ids":["rice","maize"]})
    assert response.status_code==503
    assert response.json()=={"detail":"Reference data is unavailable."}

def test_rotation_rule_invalid_window_note_is_data_error(tmp_path, monkeypatch):
    rules=json.loads(decision.RULES.read_text(encoding="utf-8"))
    rules["planting_windows"]["maize"]["note"]=[]
    path=tmp_path/"rotation_rules.json"
    path.write_text(json.dumps(rules),encoding="utf-8")
    monkeypatch.setattr(decision,"RULES",path)
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1,"planting_date":"2024-11-01"},"strategy":"current_practice","candidate_crop_ids":["maize"]})
    assert response.status_code==503
    assert response.json()=={"detail":"Reference data is unavailable."}

def test_invalid_soil_profile_status_is_data_error(tmp_path, monkeypatch):
    soil=tmp_path/"data/processed/soil/soilgrids_profile.json"
    soil.parent.mkdir(parents=True)
    soil.write_text(json.dumps({"status":[]}),encoding="utf-8")
    monkeypatch.setattr(decision,"ROOT",tmp_path)
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1},"strategy":"current_practice","candidate_crop_ids":["rice"]})
    assert response.status_code==503
    assert response.json()=={"detail":"Reference data is unavailable."}

def test_climate_summary_invalid_date_string_is_data_error(tmp_path, monkeypatch):
    summary=tmp_path/"climate_summary.json"
    summary.write_text(json.dumps({"period":{"start":"spring","end":"20251231"}}),encoding="utf-8")
    monkeypatch.setattr(decision,"CLIMATE",summary)
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"rice","farm_area_ha":1},"strategy":"current_practice"})
    assert response.status_code==503
    assert response.json()=={"detail":"Climate summary data is unavailable."}
