"""NASA GLDAS-2.1 Noah 3-hourly ingestion for Can Gio.

GLDAS fields are model land-surface estimates, not direct evaporation from salt
ponds and not a weather forecast. Fluxes are aggregated to UTC days.
"""
from __future__ import annotations
import argparse, json, logging, os, time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import numpy as np
import pandas as pd
import requests

LOGGER = logging.getLogger(__name__)
SHORT_NAME = "GLDAS_NOAH025_3H"
VERSION = "2.1"
CMR_URL = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
BBOX = (106.7, 10.2, 107.2, 10.7)
VARIABLES = ("Evap_tavg", "Rainf_tavg", "Tair_f_inst", "Qair_f_inst", "Wind_f_inst", "SWdown_f_tavg", "LWdown_f_tavg")
OUTPUT = ["date", "latitude", "longitude", "evap_mm_day", "precipitation_mm_day", "temperature_c", "specific_humidity_kg_kg", "wind_m_s", "shortwave_w_m2", "longwave_w_m2", "source", "product_version", "quality_flag"]
EXPECTED_UNITS = {"Evap_tavg": "kg m-2 s-1", "Rainf_tavg": "kg m-2 s-1", "Tair_f_inst": "K", "Qair_f_inst": "kg kg-1", "Wind_f_inst": "m s-1", "SWdown_f_tavg": "W m-2", "LWdown_f_tavg": "W m-2"}

def _ea():
    try:
        import earthaccess
        return earthaccess
    except ImportError as exc: raise RuntimeError("earthaccess is required") from exc

def login():
    ea = _ea(); strategy = "environment" if os.getenv("EARTHDATA_TOKEN") else "all"; auth = ea.login(strategy=strategy, persist=False)
    if not getattr(auth, "authenticated", False): raise RuntimeError("Earthdata authentication failed")
    return auth

def _cmr_get(params: dict[str, Any], retries: int = 3) -> dict[str, Any]:
    last = None
    with requests.Session() as session:
        for attempt in range(retries):
            try:
                r = session.get(CMR_URL, params=params, timeout=30); r.raise_for_status(); return r.json()
            except requests.HTTPError as exc:
                last = exc; status = exc.response.status_code if exc.response is not None else 0
                if status not in (429,) and not 500 <= status < 600: break
            except (requests.Timeout, requests.ConnectionError, ValueError) as exc: last = exc
            if attempt + 1 < retries: time.sleep(2**attempt)
    raise RuntimeError(f"GLDAS CMR discovery failed: {last}") from last

def discover(start: str, end: str, bbox: tuple[float, float, float, float] = BBOX) -> list[Any]:
    params = {"short_name": SHORT_NAME, "version": VERSION, "temporal": f"{start}T00:00:00Z,{end}T23:59:59Z", "bounding_box": ",".join(map(str, bbox)), "page_size": 100, "page_num": 1}
    result: list[Any] = []; seen: set[str] = set()
    while True:
        page = _cmr_get(params).get("items", [])
        for item in page:
            umm = item.get("umm", {})
            meta = item.get("meta", {})
            key = str(meta.get("concept-id") or umm.get("GranuleUR"))
            if key in seen: continue
            if not umm.get("RelatedUrls") or not meta.get("provider-id"): raise RuntimeError("GLDAS CMR item missing meta or RelatedUrls")
            from earthaccess.results import DataGranule
            result.append(DataGranule({"meta": meta, "umm": umm})); seen.add(key)
        if len(page) < 100: break
        params["page_num"] += 1
        if params["page_num"] > 1000: raise RuntimeError("GLDAS CMR pagination safety limit exceeded")
    return result

def _links(granule: Any) -> list[str]:
    links = granule.data_links() if callable(getattr(granule, "data_links", None)) else []
    return [x for x in links if isinstance(x, str) and urlparse(x).scheme == "https" and urlparse(x).path.lower().endswith((".nc4", ".nc"))]

def _valid_netcdf(path: Path) -> bool:
    """Reject HTML/login pages and incomplete non-NetCDF downloads."""
    try:
        with path.open("rb") as handle:
            return handle.read(8) == b"\x89HDF\r\n\x1a\n"
    except OSError:
        return False

def download(granules: list[Any], raw_dir: Path, checkpoint: Path | None = None) -> list[Path]:
    ea = _ea(); raw_dir.mkdir(parents=True, exist_ok=True); paths = []
    completed = set()
    if checkpoint and checkpoint.exists():
        try: completed = set(json.loads(checkpoint.read_text(encoding="utf-8")).get("completed", []))
        except (OSError, ValueError): LOGGER.warning("Ignoring unreadable GLDAS checkpoint: %s", checkpoint)
    for granule in granules:
        links = _links(granule)
        if not links: raise RuntimeError("GLDAS granule has no HTTPS NetCDF link")
        name = Path(urlparse(links[0]).path).name; target = raw_dir / name
        if target.exists() and _valid_netcdf(target):
            paths.append(target); completed.add(name)
            continue
        got = ea.download(granule, local_path=str(raw_dir)); got = got[0] if isinstance(got, (list, tuple)) else got; path = Path(got)
        if not path.exists() or path.stat().st_size == 0 or not _valid_netcdf(path):
            raise RuntimeError(f"GLDAS download failed or was not NetCDF4: {name}")
        paths.append(path); completed.add(name)
        if checkpoint:
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            checkpoint.write_text(json.dumps({"dataset": SHORT_NAME, "completed": sorted(completed)}, indent=2), encoding="utf-8")
        LOGGER.info("GLDAS download progress: %d/%d", len(paths), len(granules))
    return paths

def _find_coord(ds: Any, names: tuple[str, ...]) -> str:
    for name in names:
        if name in ds.coords or name in ds: return name
    raise ValueError(f"Missing coordinate; expected one of {names}")

def extract_file(path: Path, bbox: tuple[float, float, float, float] = BBOX) -> pd.DataFrame:
    import xarray as xr
    with xr.open_dataset(path, engine=None, decode_times=True) as ds:
        missing = [v for v in VARIABLES if v not in ds]
        if missing: raise ValueError(f"GLDAS missing variables: {missing}")
        lat, lon = _find_coord(ds, ("lat", "latitude")), _find_coord(ds, ("lon", "longitude"))
        for var, expected in EXPECTED_UNITS.items():
            unit = str(ds[var].attrs.get("units", ""));
            if unit.replace("^", "") != expected.replace("^", ""): raise ValueError(f"Unexpected {var} units: {unit!r}, expected {expected!r}")
        lat_values = ds[lat]; lon_values = ds[lon]
        selected = ds.sel({lat: lat_values.where((lat_values >= bbox[1]) & (lat_values <= bbox[3]), drop=True), lon: lon_values.where((lon_values >= bbox[0]) & (lon_values <= bbox[2]), drop=True)})
        if selected[lat].size == 0 or selected[lon].size == 0: raise ValueError("No GLDAS grid cells intersect bounding box")
        frame = selected[ list(VARIABLES) ].mean(dim=[lat, lon], skipna=True).to_dataframe().reset_index()
        time_col = "time" if "time" in frame else next(c for c in frame if c.lower() == "time")
        frame["date"] = pd.to_datetime(frame[time_col], utc=True).dt.strftime("%Y-%m-%d")
        frame["latitude"] = float(selected[lat].mean()); frame["longitude"] = float(selected[lon].mean())
        frame["evap_mm"] = frame["Evap_tavg"] * 10800 / 1.0; frame["precip_mm"] = frame["Rainf_tavg"] * 10800; frame["Tair_c"] = frame["Tair_f_inst"] - 273.15
        return frame

def aggregate_daily(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames: return pd.DataFrame(columns=OUTPUT)
    f = pd.concat(frames, ignore_index=True); grouped = f.groupby(["date", "latitude", "longitude"], as_index=False).agg(evap_mm_day=("evap_mm", "sum"), precipitation_mm_day=("precip_mm", "sum"), temperature_c=("Tair_c", "mean"), specific_humidity_kg_kg=("Qair_f_inst", "mean"), wind_m_s=("Wind_f_inst", "mean"), shortwave_w_m2=("SWdown_f_tavg", "mean"), longwave_w_m2=("LWdown_f_tavg", "mean"))
    grouped["source"] = "NASA GLDAS Noah Land Surface Model L4"; grouped["product_version"] = VERSION; grouped["quality_flag"] = "valid"; return grouped[OUTPUT]

def quality(frame: pd.DataFrame, files: list[Path], start: str, end: str, bbox: tuple[float, float, float, float], granules: int) -> dict[str, Any]:
    expected = pd.date_range(start, end, freq="D"); dates = set(pd.to_datetime(frame["date"])) if not frame.empty else set()
    return {"dataset": SHORT_NAME, "version": VERSION, "source": "NASA GES DISC", "start": start, "end": end, "bbox": bbox, "expected_days": len(expected), "days_with_data": len(dates), "missing_days": len(set(expected.strftime("%Y-%m-%d")) - set(frame["date"]) if not frame.empty else set(expected.strftime("%Y-%m-%d"))), "files_expected": granules, "files_downloaded": len(files), "grid_cells": int(frame[["latitude", "longitude"]].drop_duplicates().shape[0]) if not frame.empty else 0, "duplicate_records": int(frame.duplicated(["date", "latitude", "longitude"]).sum()), "missing_values": frame.isna().sum().to_dict(), "units": EXPECTED_UNITS, "conversion": {"Evap_tavg": "kg m-2 s-1 * 10800 s per 3-hour timestep -> mm per timestep, then UTC daily sum", "Rainf_tavg": "kg m-2 s-1 * 10800 s per 3-hour timestep -> mm per timestep, then UTC daily sum", "Tair_f_inst": "K - 273.15 -> degC", "Qair_f_inst": "kg kg-1 unchanged", "Wind_f_inst": "m s-1 unchanged", "SWdown_f_tavg": "W m-2 unchanged; UTC daily mean flux", "LWdown_f_tavg": "W m-2 unchanged; UTC daily mean flux"}, "aggregation": "mean over grid cells in bbox; UTC daily; sums for Evap/Rain rates and means for state/flux variables", "limitations": "GLDAS is model land-surface output, not direct salt-pond evaporation or a future weather forecast.", "raw_files": [str(x) for x in files]}

def run(start: str, end: str, bbox: tuple[float, float, float, float], output_dir: Path) -> pd.DataFrame:
    login(); granules = discover(start, end, bbox)
    checkpoint = output_dir / "raw" / "gldas" / ".checkpoint.json"
    files = download(granules, output_dir / "raw" / "gldas", checkpoint)
    frames = [extract_file(p, bbox) for p in files]; result = aggregate_daily(frames)
    out = output_dir / "processed" / "gldas"; out.mkdir(parents=True, exist_ok=True)
    start_tag, end_tag = start.replace("-", ""), end.replace("-", "")
    suffix = "" if (start, end) == ("2025-01-01", "2025-12-31") else f"_{start_tag}_{end_tag}"
    csv_path, report_path = out / f"gldas_daily_2025{suffix}.csv", out / f"gldas_quality_report{suffix}.json"
    result.to_csv(csv_path, index=False)
    report = quality(result, files, start, end, bbox, len(granules)); report["checkpoint"] = str(checkpoint); report["subset"] = {"method": "local spatial selection from original NASA granules", "server_side_verified": False, "reason": "GES DISC subset service endpoint was not assumed without verified collection metadata"}
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    LOGGER.info("GLDAS outputs: %s and %s", csv_path, report_path)
    return result

def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument("--start", default="2025-01-01"); p.add_argument("--end", default="2025-12-31"); p.add_argument("--west", type=float, default=BBOX[0]); p.add_argument("--south", type=float, default=BBOX[1]); p.add_argument("--east", type=float, default=BBOX[2]); p.add_argument("--north", type=float, default=BBOX[3]); p.add_argument("--output-dir", type=Path, default=Path("data")); a=p.parse_args(); print(f"Wrote {len(run(a.start,a.end,(a.west,a.south,a.east,a.north),a.output_dir))} daily rows")
if __name__ == "__main__": main()
