from datetime import date

import json

from app.services.location_data import _find_cached_climate_artifact, configured_climate_period
from datascience.power_parameters import PARAMETERS


def test_default_climate_period_tracks_last_complete_month(monkeypatch):
    monkeypatch.delenv("LOCATION_CLIMATE_END", raising=False)
    monkeypatch.setenv("LOCATION_CLIMATE_START", "20200101")

    assert configured_climate_period(today=date(2026, 11, 15)) == (
        "20200101",
        "20261031",
    )


def test_explicit_climate_period_environment_overrides_default(monkeypatch):
    monkeypatch.setenv("LOCATION_CLIMATE_START", "20240101")
    monkeypatch.setenv("LOCATION_CLIMATE_END", "20251231")

    assert configured_climate_period(today=date(2026, 11, 15)) == (
        "20240101",
        "20251231",
    )


def test_location_cache_reuses_latest_valid_artifact_across_refresh_periods(tmp_path):
    cache_root = tmp_path / "data/processed/location_cache"
    for cache_id, end in (("older", "20251231"), ("newer", "20261031")):
        cache = cache_root / cache_id
        cache.mkdir(parents=True)
        summary = {
            "location": {"latitude": 10.383333, "longitude": 105.45},
            "period": {"start": "20200101", "end": end},
            "parameters": list(PARAMETERS),
            "quality": {"coverage": {"valid": True}},
        }
        (cache / "climate_summary.json").write_text(json.dumps(summary), encoding="utf-8")
        (cache / "nasa_power_daily.csv").write_text("date\n", encoding="utf-8")

    cached_dir, artifact = _find_cached_climate_artifact(
        tmp_path, 10.383333, 105.45, "20200101"
    )

    assert cached_dir == cache_root / "newer"
    assert artifact["period"]["end"] == "20261031"
