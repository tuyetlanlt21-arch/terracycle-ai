import json
from pathlib import Path

from datascience import power, soilgrids

class FakeResponse:
    def __init__(self, payload): self.payload = payload
    def raise_for_status(self): pass
    def json(self): return self.payload

def power_payload():
    values = {name: {"20250101": 1, "20250102": 2} for name in power.PARAMETERS}
    return {"properties": {"parameter": values}, "geometry": {"coordinates": [105.45, 10.38]}}

def test_power_cache_is_location_and_period_scoped(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(power.requests, "get", lambda *a, **k: (calls.append(k["params"]) or FakeResponse(power_payload())))
    first = power.fetch_location(10.38, 105.45, "20250101", "20250102", cache_dir=tmp_path)
    second = power.fetch_location(10.38, 105.45, "20250101", "20250102", cache_dir=tmp_path)
    other = power.fetch_location(10.39, 105.45, "20250101", "20250102", cache_dir=tmp_path)
    assert first["location"] == {"latitude": 10.38, "longitude": 105.45}
    assert second["daily"] == first["daily"] and len(calls) == 2
    assert other["location"]["latitude"] == 10.39

def test_soilgrids_null_values_are_no_data(monkeypatch):
    payload = {"properties": {"layers": [{"name": "phh2o", "unit_measure": {"d_factor": 10}, "depths": [{"label": "0-5cm", "values": {"mean": None}}]}]}}
    monkeypatch.setattr(soilgrids.requests, "get", lambda *a, **k: FakeResponse(payload))
    result = soilgrids.fetch_location(10.38, 105.45, retries=1)
    assert result["availability"] == "no_data"
    assert result["status"] == "no_values"

def test_soilgrids_network_failure_is_explicit(monkeypatch):
    def fail(*args, **kwargs): raise soilgrids.requests.Timeout("offline")
    monkeypatch.setattr(soilgrids.requests, "get", fail)
    result = soilgrids.fetch_location(10.38, 105.45, retries=1)
    assert result["status"] == "network_error"
    assert result["availability"] == "unavailable"
