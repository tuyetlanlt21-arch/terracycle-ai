from pathlib import Path


def test_smoke_uses_positive_cmr_count_and_downloads_one_granule():
    source = Path(__file__).with_name("smoke_imerg_download.py").read_text(encoding="utf-8")
    assert "from datascience.imerg import DEFAULT_BBOX, discover" in source
    assert "search_data(" not in source
    assert "discover(" in source
    assert "earthaccess.download(granules[0]" in source
    assert "search_data(count=1" not in source
