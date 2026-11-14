import json
from pathlib import Path
import pytest
from datascience.rotation_rules import evaluate, load_catalog, load_rules
from datascience.soilgrids import normalize

ROOT=Path(__file__).parents[2]
def test_catalog_has_four_traceable_crops_and_explicit_mung_water_gap():
    catalog=load_catalog(ROOT/"data/reference/crop_catalog.json"); assert {x["crop_id"] for x in catalog["records"]}=={"rice","maize","mung_bean","soybean"}
    mung=next(x for x in catalog["records"] if x["crop_id"]=="mung_bean"); assert mung["water_requirement"]["min_mm_season"] is None
def test_empty_catalog_is_not_valid():
    path=ROOT/".pytest-tmp-empty-catalog.json"; path.write_text(json.dumps({"status":"unavailable_no_verified_export_in_repository","records":[]}),encoding="utf-8")
    try:
        with pytest.raises(ValueError): load_catalog(path)
    finally: path.unlink(missing_ok=True)
def test_every_rotation_rule_is_sourced_and_unknown_is_not_pass():
    rules=load_rules(ROOT/"data/reference/rotation_rules.json"); assert all(rule["source_urls"] for rule in rules["compatibility"])
    result=evaluate({"requires_water_plan":True},water_available=None,soil_ph=None,soil_ec=None); assert result["hard_constraints_pass"] is True; assert result["scoreable"] is False
def test_soilgrids_nulls_are_preserved():
    payload={"properties":{"layers":[{"name":"phh2o","unit_measure":{"d_factor":10,"target_units":"-"},"depths":[{"label":"0-5cm","values":{"mean":None}}]}]}}
    result=normalize(payload,10.383333,105.45); assert result["status"]=="no_values"; assert result["properties"][0]["values"]["0-5cm"] is None
