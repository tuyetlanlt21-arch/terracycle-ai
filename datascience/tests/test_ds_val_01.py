"""DS-VAL-01 independent validation of the decision entry point and contract."""

import json

import pytest
from pydantic import ValidationError

from app.models import FarmProfile, RotationScenario
from app.services.decision import compare_rotation


def farm(**overrides):
    data = {
        "current_crop": "rice",
        "farm_area_ha": 1,
        "soil_ph": 6.0,
        "soil_salinity_ec": 1.0,
        "irrigation_water_ec": 0.5,
        "irrigation_available": True,
        "freshwater_availability": "adequate",
        "farmer_priority": "yield",
        "planning_month": 11,
        "planting_date": "2024-11-01",
    }
    data.update(overrides)
    return FarmProfile.model_validate(data)


def result(strategy, candidates=("rice",), **farm_overrides):
    return compare_rotation(
        RotationScenario(
            farm=farm(**farm_overrides),
            strategy=strategy,
            candidate_crop_ids=list(candidates),
        )
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("current_crop", ""),
        ("farm_area_ha", 0),
        ("soil_ph", 14.1),
        ("soil_salinity_ec", -0.1),
        ("irrigation_water_ec", -0.1),
        ("freshwater_availability", "plentiful"),
        ("farmer_priority", "profit"),
        ("planning_month", 13),
        ("planting_date", "not-a-date"),
    ],
)
def test_farm_profile_rejects_invalid_values(field, value):
    with pytest.raises(ValidationError):
        farm(**{field: value})


def test_farm_profile_accepts_null_optional_measurements():
    profile = farm(soil_ph=None, soil_salinity_ec=None, irrigation_water_ec=None, planting_date=None)
    assert profile.soil_ph is None
    assert profile.planting_date is None


@pytest.mark.parametrize(
    "strategy,expected_phrase",
    [
        ("current_practice", "baseline continuation"),
        ("water_saving", "water-saving ranking"),
        ("soil_recovery", "soil-recovery ranking"),
    ],
)
def test_all_strategies_return_contract_fields_and_strategy_rationale(strategy, expected_phrase):
    response = result(strategy)
    item = response.recommendations[0]
    assert item.strategy == strategy
    assert set(item.suitability) == {"temperature", "rainfall_window", "water", "soil", "salinity"}
    assert any(expected_phrase in text for text in item.rationale)


def test_unknown_evidence_is_not_scored_and_warnings_are_actionable():
    response = result(
        "water_saving",
        ("mung_bean",),
        soil_ph=None,
        soil_salinity_ec=None,
        irrigation_available=None,
        freshwater_availability="unknown",
    )
    item = response.recommendations[0]
    assert item.eligibility == "UNKNOWN"
    assert item.score is None
    assert "UNKNOWN" in {item.eligibility, item.hard_constraints_pass}
    assert item.warnings
    assert response.missing_data_warnings
    assert any("water" in warning.lower() for warning in item.warnings)


def test_failures_are_rejected_with_reasons_and_no_recommendation():
    response = result(
        "water_saving",
        ("rice",),
        soil_salinity_ec=4.0,
        irrigation_available=False,
        freshwater_availability="limited",
    )
    assert response.recommendations == []
    assert response.rejected_alternatives
    rejected = response.rejected_alternatives[0]
    assert rejected.eligibility == "FAIL"
    assert any("salinity" in reason.lower() for reason in rejected.reasons)
    assert rejected.sources


def test_transition_status_and_unsupported_candidate_are_explicit():
    incompatible = result("current_practice", ("maize",))
    assert incompatible.rejected_alternatives[0].eligibility == "FAIL"
    assert any("transition" in reason for reason in incompatible.rejected_alternatives[0].reasons)

    unsupported = result("current_practice", ("cassava",))
    assert unsupported.rejected_alternatives[0].eligibility == "FAIL"
    assert any("catalog" in reason for reason in unsupported.rejected_alternatives[0].reasons)


def test_evidence_sources_are_deduplicated_and_provenance_is_present():
    response = result("soil_recovery", ("rice", "soybean"))
    for item in response.recommendations:
        assert item.sources == sorted(set(item.sources))
        assert all(source.startswith("http") for source in item.sources)
    assert response.provenance["climate_source"] == "NASA POWER"
    assert response.provenance["forecast_available"] is False
    assert response.provenance["climate_period"]
    assert "score_definition" in response.scoring


def test_json_output_matches_current_api_contract():
    response = result("current_practice")
    body = json.loads(response.model_dump_json())
    assert set(body) == {
        "recommendations",
        "rejected_alternatives",
        "missing_data_warnings",
        "warnings",
        "provenance",
        "scoring",
    }
    item = body["recommendations"][0]
    assert {"sequence", "crop_id", "crop_name", "strategy", "eligibility", "score", "growth_duration_days", "hard_constraints_pass", "suitability", "rationale", "warnings", "sources"} <= set(item)
    assert isinstance(item["sources"], list)
    assert item["score"] is None or isinstance(item["score"], (float, int))

