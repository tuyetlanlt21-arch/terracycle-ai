from pathlib import Path
import pandas as pd
import pytest
from datascience import gldas


def _umm_item(name="G1"):
    return {"meta": {"concept-id": name, "provider-id": "GES_DISC"}, "umm": {"GranuleUR": name, "RelatedUrls": [{"URL": f"https://data.gesdisc.earthdata.nasa.gov/{name}.nc4", "Type": "GET DATA"}]}}


def test_cmr_umm_pagination_and_datagranule(monkeypatch):
    calls = []
    def fake(params):
        calls.append(dict(params)); return {"items": [_umm_item("G1"), _umm_item("G2")]} if len(calls) == 1 else {"items": []}
    monkeypatch.setattr(gldas, "_cmr_get", fake)
    result = gldas.discover("2025-01-01", "2025-01-07")
    assert len(result) == 2 and result[0].data_links()[0].endswith("G1.nc4") and calls[0]["page_size"] == 100


def test_water_flux_conversion_and_daily_aggregation():
    frame = pd.DataFrame({"date": ["2025-01-01", "2025-01-01"], "latitude": [10.3, 10.3], "longitude": [106.8, 106.8], "evap_mm": [1.0, 2.0], "precip_mm": [3.0, 4.0], "Tair_c": [27.0, 29.0], "Qair_f_inst": [.01, .02], "Wind_f_inst": [1., 3.], "SWdown_f_tavg": [100., 200.], "LWdown_f_tavg": [50., 70.]})
    out = gldas.aggregate_daily([frame])
    assert len(out) == 1 and out.loc[0, "evap_mm_day"] == 3 and out.loc[0, "precipitation_mm_day"] == 7 and out.loc[0, "temperature_c"] == 28


def test_quality_report_missing_and_duplicates():
    frame = pd.DataFrame(columns=gldas.OUTPUT)
    report = gldas.quality(frame, [], "2025-01-01", "2025-01-02", gldas.BBOX, 2)
    assert report["expected_days"] == 2 and report["missing_days"] == 2 and report["files_downloaded"] == 0


def test_missing_variable_fails():
    xr = pytest.importorskip("xarray")
    tmp_path = Path("datascience/tests/_tmp_gldas")
    tmp_path.mkdir(exist_ok=True)
    path = tmp_path / "bad.nc"
    ds = xr.Dataset({"Evap_tavg": (("lat", "lon"), [[1.]])}, coords={"lat": [10.3], "lon": [106.8]})
    ds.to_netcdf(path)
    with pytest.raises(ValueError, match="missing variables"):
        gldas.extract_file(path)
    path.unlink(); tmp_path.rmdir()


def test_extract_valid_units_and_flux_conversion():
    xr = pytest.importorskip("xarray")
    path = Path("datascience/tests/_valid_gldas.nc")
    coords = {"time": pd.date_range("2025-01-01", periods=2, freq="3h"), "lat": [10.3, 10.8], "lon": [106.8, 107.1]}
    ds = xr.Dataset({v: (("time", "lat", "lon"), [[[1.0, 1.0], [1.0, 1.0]]] * 2) for v in gldas.VARIABLES}, coords=coords)
    for v, unit in gldas.EXPECTED_UNITS.items(): ds[v].attrs["units"] = unit
    ds.to_netcdf(path)
    try:
        frame = gldas.extract_file(path)
        assert len(frame) == 2 and frame["evap_mm"].iloc[0] == 10800 and frame["Tair_c"].iloc[0] == pytest.approx(-272.15)
    finally:
        path.unlink(missing_ok=True)
