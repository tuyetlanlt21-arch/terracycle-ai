"""Real NASA Earthdata smoke test; never uses mock data.

Run from repository root:
    python datascience/tests/smoke_imerg_download.py
"""
from __future__ import annotations

import os
import sys
import logging
import traceback
from pathlib import Path

# When invoked as ``python datascience/tests/smoke_imerg_download.py``, Python
# places only this tests directory on sys.path. Add the repository root solely
# for direct-script compatibility; module execution needs no bootstrap.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd

LOGGER = logging.getLogger("smoke_imerg_download")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not os.getenv("EARTHDATA_TOKEN"):
        LOGGER.error("stage=Earthdata login result=FAIL reason=EARTHDATA_TOKEN is not set")
        return 2
    try:
        import earthaccess
        import xarray as xr
        from datascience.imerg import DEFAULT_BBOX, discover
        LOGGER.info("stage=Earthdata login status=START")
        auth = earthaccess.login(strategy="environment", persist=False)
        if not auth.authenticated: raise RuntimeError("Earthdata authentication returned authenticated=False")
        LOGGER.info("stage=Earthdata login status=PASS authenticated=True")
        LOGGER.info("stage=CMR discovery status=START short_name=GPM_3IMERGDF version=07 date=2025-01-01")
        granules = discover("2025-01-01", "2025-01-01", DEFAULT_BBOX)
        if not granules: raise RuntimeError("CMR returned no IMERG V07 granule for 2025-01-01")
        LOGGER.info("stage=CMR discovery status=PASS granules_found=%d", len(granules))
        out = Path("data/raw/imerg/smoke")
        out.mkdir(parents=True, exist_ok=True)
        LOGGER.info("stage=earthaccess.download status=START granule_count=1")
        paths = earthaccess.download(granules[0], local_path=str(out))
        path = Path(paths[0] if isinstance(paths, (list, tuple)) else paths)
        if not path.exists() or path.stat().st_size == 0: raise RuntimeError("downloaded file is missing or empty")
        LOGGER.info("stage=earthaccess.download status=PASS file=%s size_bytes=%d", path.name, path.stat().st_size)
        LOGGER.info("stage=NetCDF validation status=START file=%s", path.name)
        with path.open("rb") as stream:
            if stream.read(8) != b"\x89HDF\r\n\x1a\n": raise RuntimeError("downloaded file is not HDF5/NetCDF4")
        with xr.open_dataset(path) as ds:
            variables = [name for name in ("precipitation", "precipitationCal", "precipitationCalSurface", "precipitationUncal") if name in ds]
            if not variables: raise RuntimeError("no IMERG precipitation variable found")
            LOGGER.info("stage=NetCDF validation status=PASS variable=%s coords=%s dims=%s", variables[0], list(ds.coords), dict(ds.dims))
            print(f"PASS: {path} ({path.stat().st_size} bytes), variable={variables[0]}, coords={list(ds.coords)}, dims={dict(ds.dims)}")
        return 0
    except Exception as exc:
        LOGGER.error("stage=smoke test status=FAIL error_type=%s error=%s", type(exc).__name__, str(exc)[:300])
        traceback.print_exc()
        print(f"FAIL: real IMERG smoke test failed: {type(exc).__name__}: {str(exc)[:300]}")
        return 1


if __name__ == "__main__": sys.exit(main())
