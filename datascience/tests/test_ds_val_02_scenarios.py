"""Scenario-based validation for Can Gio; expected assertions come from rules, not snapshots."""

import json
from pathlib import Path

import pytest

from app.models import FarmProfile, RotationScenario
from app.services.decision import compare_rotation


FIXTURE = Path(__file__).parent / "fixtures" / "ds_val_02_can_gio.json"
DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("scenario", DATA["scenarios"], ids=lambda s: s["id"])
@pytest.mark.parametrize("strategy", DATA["strategies"])
def test_can_gio_scenario_strategy_matrix(scenario, strategy):
    profile = FarmProfile.model_validate(scenario["farm"])
    response = compare_rotation(RotationScenario(farm=profile, strategy=strategy, candidate_crop_ids=scenario["candidate_crop_ids"]))
    expected = scenario["expected"]
    items = [*response.recommendations, *response.rejected_alternatives]
    item = next(item for item in items if item.crop_id == expected["target"])

    # Rule-derived expectations, intentionally independent of ranking order.
    if "eligibility" in expected:
        assert item.eligibility == expected["eligibility"]
    if "score" in expected:
        assert getattr(item, "score", None) is expected["score"]
    if hasattr(item, "suitability"):
        for dimension, status in expected.get("suitability", {}).items():
            assert item.suitability[dimension] == status
    else:
        # RejectedAlternative intentionally exposes reasons/sources, not suitability.
        assert expected["reason_contains"].lower() in " ".join(item.reasons).lower()
    if hasattr(item, "rationale"):
        assert any(expected["reason_contains"].lower() in text.lower() for text in [*item.rationale, *item.warnings])

    assert item.sequence == [profile.current_crop, item.crop_id]
    assert response.provenance["climate_source"] == "NASA POWER"
    assert response.provenance["forecast_available"] is False
    assert response.warnings
    if item.eligibility == "FAIL":
        assert item in response.rejected_alternatives
    if item.eligibility == "UNKNOWN":
        assert item.warnings or response.missing_data_warnings


def test_six_scenarios_have_three_strategy_runs_and_are_not_field_observations():
    assert len(DATA["scenarios"]) == 6
    assert len(DATA["strategies"]) == 3
    assert "Synthetic" in DATA["source_policy"]
