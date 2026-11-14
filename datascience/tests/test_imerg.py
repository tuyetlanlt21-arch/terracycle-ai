import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from datascience import imerg


def test_discovery_uses_public_cmr_and_pagination(monkeypatch):
    calls = []
    def fake_get(url, params, token=None, retries=3):
        calls.append((url, dict(params), token))
        if params["page_num"] == 1: return {"items": [{"meta": {"provider-id": "GES_DISC"}, "umm": {"GranuleUR": str(i), "RelatedUrls": [{"URL": f"https://data.gesdisc.earthdata.nasa.gov/data/{i}.nc4", "Type": "GET DATA"}]}} for i in range(100)]}
        return {"items": [{"meta": {"provider-id": "GES_DISC"}, "umm": {"GranuleUR": "G2", "RelatedUrls": [{"URL": "https://data.gesdisc.earthdata.nasa.gov/data/G2.nc4", "Type": "GET DATA"}]}}]}
    monkeypatch.setattr(imerg, "_cmr_get", fake_get)
    result = imerg._discover_cmr("2025-01-01", "2025-01-07", imerg.DEFAULT_BBOX)
    assert len(result) == 101 and calls[0][1]["page_num"] == 1 and calls[1][1]["page_num"] == 2
    assert all(token is None for _, _, token in calls)


def test_cmr_get_does_not_send_bearer_and_does_not_retry_400(monkeypatch):
    class Response:
        status_code = 400; url = "https://cmr.example"
        def raise_for_status(self): raise __import__("requests").HTTPError(response=self)
    calls = []
    class Session:
        def get(self, *args, **kwargs): calls.append(kwargs); return Response()
    monkeypatch.setattr(imerg.requests, "Session", lambda: Session())
    with pytest.raises(RuntimeError): imerg._cmr_get("https://cmr.example", {"page_size": 1}, retries=3)
    assert len(calls) == 1 and calls[0]["headers"] == {} and calls[0]["allow_redirects"] is True


def test_cmr_discovery_uses_positive_page_size(monkeypatch):
    seen = []
    def fake_get(url, params, token=None, retries=3):
        seen.append((url, params))
        return {"items": [{"meta": {"provider-id": "GES_DISC"}, "umm": {"GranuleUR": "G123", "RelatedUrls": [{"URL": "https://data.gesdisc.earthdata.nasa.gov/data/G123.nc4", "Type": "GET DATA"}]}}]}
    monkeypatch.setattr(imerg, "_cmr_get", fake_get)
    result = imerg.discover("2025-01-01", "2025-01-07")
    assert len(result) == 1
    assert seen[0][1]["page_size"] == 100


def test_umm_fixture_builds_data_granule_and_data_links(monkeypatch):
    umm = {"GranuleUR": "G3578705258-GES_DISC", "Temporal": {"RangeDateTime": {"BeginningDateTime": "2025-01-01T00:00:00Z"}}, "RelatedUrls": [{"URL": "https://data.gesdisc.earthdata.nasa.gov/data/G3578705258.nc4", "Type": "GET DATA"}]}
    monkeypatch.setattr(imerg, "_cmr_get", lambda *args, **kwargs: {"items": [{"meta": {"provider-id": "GES_DISC"}, "umm": umm}]})
    granule = imerg._discover_cmr("2025-01-01", "2025-01-01", imerg.DEFAULT_BBOX)[0]
    assert granule.data_links() == ["https://data.gesdisc.earthdata.nasa.gov/data/G3578705258.nc4"]
    assert imerg._download_links(granule) == ["https://data.gesdisc.earthdata.nasa.gov/data/G3578705258.nc4"]


def test_authentication_failure(monkeypatch):
    class EA:
        def login(self, **kwargs): raise RuntimeError("401")
    monkeypatch.setattr(imerg, "_earthaccess", lambda: EA())
    with pytest.raises(RuntimeError, match="401"): imerg.login_earthdata()


def test_download_failure():
    tmp_path = Path("datascience/tests/_tmp_imerg")
    class EA:
        def download(self, *args, **kwargs): raise OSError("network")
    try:
        with pytest.raises(RuntimeError, match="download failed"):
            imerg.download_granules([SimpleNamespace(data_links=lambda: ["https://x/a.h5"])], tmp_path, EA())
    finally:
        tmp_path.rmdir()


def test_cmr_dictionary_extracts_https_data_link_and_streams(monkeypatch):
    target_dir = Path("datascience/tests/_tmp_imerg")
    granule = {"id": "G123", "links": [
        {"rel": "http://esipfed.org/ns/fedsearch/1.1/metadata#", "href": "https://example.test/meta"},
        {"rel": "http://esipfed.org/ns/fedsearch/1.1/data#", "href": "https://data.gesdisc.earthdata.nasa.gov/data/file.nc4"},
        {"rel": "http://esipfed.org/ns/fedsearch/1.1/data#", "href": "s3://bucket/file.nc4"},
    ]}
    class Response:
        status_code = 200
        url = "https://data.gesdisc.earthdata.nasa.gov/data/file.nc4"
        headers = {"Content-Type": "application/octet-stream"}
        def raise_for_status(self): pass
        def iter_content(self, chunk_size): return [b"\x89HDF\r\n\x1a\n", b"def"]
        def close(self): pass
    calls = []
    class EA:
        def download(self, granule, local_path):
            path = Path(local_path) / "file.nc4"; path.write_bytes(b"\x89HDF\r\n\x1a\nxyz"); return [path]
    try:
        files = imerg.download_granules([granule], target_dir, EA())
        assert files[0].read_bytes() == b"\x89HDF\r\n\x1a\nxyz"
    finally:
        for item in target_dir.iterdir(): item.unlink()
        target_dir.rmdir()


def test_redirect_to_earthdata_login_is_classified_and_token_stays_scoped(monkeypatch):
    class Response:
        def __init__(self, status, url, headers): self.status_code, self.url, self.headers = status, url, headers
        def raise_for_status(self): pass
        def close(self): pass
        def iter_content(self, chunk_size): return [b"<html>login</html>"]
    responses = iter([Response(302, "https://goldsmr4.gesdisc.eosdis.nasa.gov/a.nc4", {"Location": "https://urs.earthdata.nasa.gov/login"}), Response(200, "https://urs.earthdata.nasa.gov/login", {"Content-Type": "text/html"})])
    calls = []
    monkeypatch.setattr(imerg, "_download_session", lambda: type("S", (), {"get": lambda self, url, **kwargs: imerg.requests.get(url, **kwargs)})())
    monkeypatch.setenv("EARTHDATA_TOKEN", "secret")
    monkeypatch.setattr(imerg.requests, "get", lambda url, **kwargs: calls.append((url, kwargs)) or next(responses))
    with pytest.raises(RuntimeError, match="Earthdata Login HTML"):
        imerg._stream_download("https://goldsmr4.gesdisc.eosdis.nasa.gov/a.nc4", Path("datascience/tests/nonexistent.nc4"))
    assert "Authorization" in calls[0][1]["headers"] and "Authorization" in calls[1][1]["headers"]


def test_html_gesdisc_error_is_not_saved(monkeypatch):
    class Response:
        status_code = 200; url = "https://goldsmr4.gesdisc.eosdis.nasa.gov/a"; headers = {"Content-Type": "text/html"}
        def raise_for_status(self): pass
        def close(self): pass
        def iter_content(self, chunk_size): return [b"<html>GES DISC error</html>"]
    monkeypatch.setattr(imerg.requests, "get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(imerg, "_download_session", lambda: type("S", (), {"get": lambda self, url, **kwargs: imerg.requests.get(url, **kwargs)})())
    target = Path("datascience/tests/nonexistent.nc4")
    with pytest.raises(RuntimeError, match="GES DISC HTML error page"):
        imerg._stream_download("https://goldsmr4.gesdisc.eosdis.nasa.gov/a.nc4", target)
    assert not target.exists()


def test_redirect_chain_302_302_301_200(monkeypatch):
    import requests
    class Response:
        def __init__(self, status, url, headers, chunks=()): self.status_code, self.url, self.headers, self._chunks = status, url, headers, chunks
        def raise_for_status(self):
            if self.status_code >= 400: raise requests.HTTPError(response=self)
        def close(self): pass
        def iter_content(self, chunk_size): return self._chunks
    responses = iter([
        Response(302, "https://data.gesdisc.earthdata.nasa.gov/a.nc4", {"Location": "https://urs.earthdata.nasa.gov/login"}),
        Response(302, "https://urs.earthdata.nasa.gov/login", {"Location": "https://data.gesdisc.earthdata.nasa.gov/b.nc4"}),
        Response(301, "https://data.gesdisc.earthdata.nasa.gov/b.nc4", {"Location": "https://data.gesdisc.earthdata.nasa.gov/c.nc4"}),
        Response(200, "https://data.gesdisc.earthdata.nasa.gov/c.nc4", {"Content-Type": "application/x-netcdf"}, [b"\x89HDF\r\n\x1a\n", b"x"]),
    ])
    monkeypatch.setattr(imerg, "_download_session", lambda: type("S", (), {"get": lambda self, url, **kwargs: next(responses)})())
    target = Path("datascience/tests/redirect.nc4")
    try:
        assert imerg._stream_download("https://data.gesdisc.earthdata.nasa.gov/a.nc4", target) == target
    finally: target.unlink(missing_ok=True)


def test_redirect_loop_and_401_fail_without_infinite_retry(monkeypatch):
    import requests
    class Response:
        status_code = 302; url = "https://data.gesdisc.earthdata.nasa.gov/a.nc4"; headers = {"Location": "https://urs.earthdata.nasa.gov/a.nc4"}
        def raise_for_status(self): pass
        def close(self): pass
        def iter_content(self, chunk_size): return []
    monkeypatch.setattr(imerg, "_download_session", lambda: type("S", (), {"get": lambda self, url, **kwargs: Response()})())
    with pytest.raises(RuntimeError, match="redirect loop"):
        imerg._stream_download("https://data.gesdisc.earthdata.nasa.gov/a.nc4", Path("datascience/tests/loop.nc4"))
    class Unauthorized(Response):
        status_code = 401; headers = {}
        def raise_for_status(self): raise requests.HTTPError(response=self)
    monkeypatch.setattr(imerg, "_download_session", lambda: type("S", (), {"get": lambda self, url, **kwargs: Unauthorized()})())
    with pytest.raises(requests.HTTPError):
        imerg._stream_download("https://data.gesdisc.earthdata.nasa.gov/a.nc4", Path("datascience/tests/401.nc4"))


def test_official_chain_to_cloudfront_uses_clean_session(monkeypatch):
    class Response:
        def __init__(self, status, url, headers, chunks=()): self.status_code, self.url, self.headers, self._chunks = status, url, headers, chunks
        def raise_for_status(self): pass
        def close(self): pass
        def iter_content(self, chunk_size): return self._chunks
    responses = iter([
        Response(302, "https://data.gesdisc.earthdata.nasa.gov/a.nc4", {"Location": "https://urs.earthdata.nasa.gov/login"}),
        Response(302, "https://urs.earthdata.nasa.gov/login", {"Location": "https://data.gesdisc.earthdata.nasa.gov/b.nc4"}),
        Response(301, "https://data.gesdisc.earthdata.nasa.gov/b.nc4", {"Location": "https://d2b3c3wh8s6en5.cloudfront.net/file.nc4"}),
        Response(200, "https://d2b3c3wh8s6en5.cloudfront.net/file.nc4", {"Content-Type": "application/octet-stream"}, [b"\x89HDF\r\n\x1a\n", b"x"]),
    ])
    sessions = []
    class Session:
        def get(self, url, **kwargs): sessions.append((url, kwargs)); return next(responses)
    monkeypatch.setattr(imerg, "_download_session", lambda: Session())
    monkeypatch.setattr(imerg.requests, "Session", lambda: Session())
    target = Path("datascience/tests/cloudfront.nc4")
    try:
        imerg._official_stream_download("https://data.gesdisc.earthdata.nasa.gov/a.nc4", target)
        assert sessions[-1][0].startswith("https://d2b3c3wh8s6en5.cloudfront.net")
        assert sessions[-1][1]["headers"] == {}
    finally: target.unlink(missing_ok=True)


def test_official_rejects_untrusted_cloudfront_redirect(monkeypatch):
    class Response:
        status_code = 302; url = "https://data.gesdisc.earthdata.nasa.gov/a.nc4"; headers = {"Location": "https://evil.example/file.nc4"}
        def close(self): pass
        def raise_for_status(self): pass
    monkeypatch.setattr(imerg, "_download_session", lambda: type("S", (), {"get": lambda self, url, **kwargs: Response()})())
    with pytest.raises(RuntimeError, match="untrusted host"):
        imerg._official_stream_download("https://data.gesdisc.earthdata.nasa.gov/a.nc4", Path("datascience/tests/bad.nc4"))


def test_earthaccess_object_uses_data_links_and_resumes(monkeypatch):
    target_dir = Path("datascience/tests/_tmp_imerg")
    target_dir.mkdir(exist_ok=True)
    target = target_dir / "file.nc4"; target.write_bytes(b"\x89HDF\r\n\x1a\nexisting")
    class Granule:
        concept_id = "E123"
        def data_links(self): return ["https://example.test/file.nc4"]
    class EA:
        def download(self, *args, **kwargs): raise AssertionError("must resume without download")
    try:
        assert imerg.download_granules([Granule()], target_dir, EA()) == [target]
    finally:
        target.unlink(); target_dir.rmdir()


def test_cmr_rejects_virtual_directory_and_non_gesdisc_links():
    granule = {"id": "G999", "links": [
        {"rel": ".../data#", "href": "https://cmr.earthdata.nasa.gov/data/"},
        {"rel": ".../data#", "href": "https://goldsmr4.gesdisc.eosdis.nasa.gov/data/file.nc4"},
        {"rel": ".../data#", "href": "https://data.gesdisc.earthdata.nasa.gov/data/file.nc4"},
    ]}
    assert imerg._download_links(granule) == ["https://data.gesdisc.earthdata.nasa.gov/data/file.nc4"]


def test_extract_units_fill_and_bbox():
    xr = pytest.importorskip("xarray")
    tmp_path = Path("datascience/tests/_tmp_imerg")
    tmp_path.mkdir(exist_ok=True)
    path = tmp_path / "20250101.nc"
    ds = xr.Dataset({"precipitation": (("lat", "lon"), [[1.0, -9999.0], [3.0, 4.0]])}, coords={"lat": [10.2, 10.8], "lon": [106.7, 107.2]})
    ds.precipitation.attrs["units"] = "mm/day"; ds.precipitation.attrs["_FillValue"] = -9999.0; ds.to_netcdf(path)
    frame = imerg.extract_file(path, (106.7, 10.2, 107.2, 10.7))
    assert len(frame) == 1 and frame.iloc[0].precipitation_mm_day == 1.0
    path.unlink(); tmp_path.rmdir()


def test_invalid_dataset_and_missing_precipitation():
    xr = pytest.importorskip("xarray")
    tmp_path = Path("datascience/tests/_tmp_imerg")
    tmp_path.mkdir(exist_ok=True)
    path = tmp_path / "bad.nc"; xr.Dataset({"temperature": ("x", [1])}).to_netcdf(path)
    with pytest.raises(RuntimeError, match="precipitation"):
        imerg.extract_file(path)
    path.unlink(); tmp_path.rmdir()


def test_hourly_conversion_and_quality():
    frame = pd.DataFrame({"date": ["2025-01-01"], "latitude": [10.3], "longitude": [106.8], "precipitation_mm_day": [2.0], "source": ["x"], "product_version": ["07"]})
    report = imerg.quality_report(frame, [Path("a.nc")], "2025-01-01", "2025-01-02", imerg.DEFAULT_BBOX, 1)
    assert report["total_days"] == 2 and report["days_with_data"] == 1 and report["days_missing"] == 1
