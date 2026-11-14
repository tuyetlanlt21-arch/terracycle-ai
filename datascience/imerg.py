"""NASA GPM IMERG Final Run (GPM_3IMERGDF) acquisition and extraction."""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import requests
from urllib.parse import urlparse

LOGGER = logging.getLogger(__name__)
SHORT_NAME = "GPM_3IMERGDF"
VERSION = "07"
CMR_GRANULES = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
DEFAULT_BBOX = (106.7, 10.2, 107.2, 10.7)
CSV_COLUMNS = ["date", "latitude", "longitude", "precipitation_mm_day", "source", "product_version"]
TRUSTED_DOWNLOAD_HOSTS = {"urs.earthdata.nasa.gov", "disc.gsfc.nasa.gov", "goldsmr4.gesdisc.eosdis.nasa.gov", "data.gesdisc.eosdis.nasa.gov", "data.gesdisc.earthdata.nasa.gov", "gpm1.gesdisc.eosdis.nasa.gov"}


def _earthaccess():
    try:
        import earthaccess
    except ImportError as exc:
        raise RuntimeError("earthaccess is required: pip install earthaccess") from exc
    return earthaccess


def login_earthdata():
    """Prefer EARTHDATA_TOKEN; never fall back to an interactive prompt when set."""
    ea = _earthaccess()
    strategy = "environment" if os.getenv("EARTHDATA_TOKEN") else "all"
    auth = ea.login(strategy=strategy, persist=False)
    if not getattr(auth, "authenticated", False):
        raise RuntimeError("Earthdata authentication did not succeed")
    LOGGER.info("Earthdata authentication succeeded")
    return auth


def _cmr_get(url: str, params: dict[str, Any], token: str | None = None, retries: int = 3) -> dict[str, Any]:
    """GET public CMR metadata without forwarding Earthdata auth by default."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    last: Exception | None = None
    session = requests.Session()
    for attempt in range(retries):
        try:
            response = session.get(url, params=params, headers=headers, timeout=30, allow_redirects=True)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            last = exc
            status = exc.response.status_code if exc.response is not None else None
            LOGGER.warning("CMR request failed status=%s url=%s params=%s", status, url, params)
            if status not in (429,) and not (status is not None and 500 <= status < 600): break
            if attempt + 1 < retries: time.sleep(2**attempt)
        except (requests.Timeout, requests.ConnectionError, ValueError) as exc:
            last = exc
            LOGGER.warning("CMR request transport/JSON failure attempt=%d/%d: %s", attempt + 1, retries, exc)
            if attempt + 1 < retries: time.sleep(2**attempt)
    raise RuntimeError(f"CMR request failed after {retries} attempts: {last}") from last


def _discover_cmr(start: str, end: str, bbox: tuple[float, float, float, float]) -> list[Any]:
    """Discover UMM granules directly; never call earthaccess.search_data()."""
    params = {"short_name": SHORT_NAME, "version": VERSION, "temporal": f"{start}T00:00:00Z,{end}T23:59:59Z", "bounding_box": ",".join(map(str, bbox)), "page_size": 100, "page_num": 1}
    granules: list[Any] = []
    seen: set[str] = set()
    while True:
        result = _cmr_get(CMR_GRANULES, params)
        page = result.get("items", [])
        if not isinstance(page, list): raise RuntimeError("CMR UMM response has no items list")
        for item in page:
            umm = item.get("umm", item) if isinstance(item, dict) else item
            if not isinstance(umm, dict): continue
            identity = str(umm.get("GranuleUR") or umm.get("Temporal", {}).get("RangeDateTime", {}).get("BeginningDateTime") or len(granules))
            if identity in seen: continue
            seen.add(identity)
            try:
                from earthaccess.results import DataGranule
                # earthaccess 0.19.0 needs both item metadata (store/provider-id)
                # and UMM payload (data_links/RelatedUrls).
                meta = item.get("meta", {}) if isinstance(item, dict) else {}
                if not isinstance(meta, dict) or not meta.get("provider-id"):
                    raise RuntimeError("CMR UMM item lacks meta.provider-id required by earthaccess")
                granules.append(DataGranule({"meta": meta, "umm": umm}))
            except ImportError as exc:
                raise RuntimeError("earthaccess is required to create DataGranule objects") from exc
        if len(page) < params["page_size"]: break
        params["page_num"] += 1
        if params["page_num"] > 1000: raise RuntimeError("CMR pagination safety limit exceeded")
    LOGGER.info("CMR UMM discovered %d granule(s)", len(granules))
    return granules


def discover(start: str, end: str, bbox: tuple[float, float, float, float] = DEFAULT_BBOX) -> list[Any]:
    try: return _discover_cmr(start, end, bbox)
    except Exception as exc: raise RuntimeError(f"IMERG CMR discovery failed: {exc}") from exc


def _granule_path(granule: Any) -> str:
    if isinstance(granule, (str, Path)): return str(granule)
    for attr in ("data_links", "data_links_url"):
        value = getattr(granule, attr, None)
        if callable(value): value = value()
        if value: return str(value[0] if isinstance(value, (list, tuple)) else value)
    return str(granule)


def _granule_id(granule: Any) -> str:
    if isinstance(granule, dict): return str(granule.get("id") or granule.get("producer_granule_id") or "unknown")
    if hasattr(granule, "get"):
        umm = granule.get("umm", {})
        return str(granule.get("meta", {}).get("concept-id") or umm.get("GranuleUR") or "unknown")
    return str(getattr(granule, "concept_id", None) or getattr(granule, "id", None) or "unknown")


def _download_links(granule: Any) -> list[str]:
    """Return validated file links; CMR inherited/virtual links are excluded."""
    is_cmr = isinstance(granule, dict)
    links = getattr(granule, "data_links", None)
    if callable(links): links = links()
    if isinstance(granule, dict): links = granule.get("links", [])
    if not links and hasattr(granule, "get"):
        # Earthaccess 0.19.0 DataGranule stores the original CMR UMM under
        # granule["umm"]; tolerate provider-specific data_links filtering.
        links = granule.get("umm", {}).get("RelatedUrls", [])
    links = links or []
    candidates = []
    for item in links:
        href = (item.get("href") or item.get("URL")) if isinstance(item, dict) else item
        rel = str(item.get("rel") or item.get("Type", "")).lower() if isinstance(item, dict) else ""
        if not isinstance(href, str): continue
        parsed = urlparse(href)
        host = (parsed.hostname or "").lower()
        filename = parsed.path.rsplit("/", 1)[-1].lower()
        if parsed.scheme.lower() != "https" or not host or not filename.endswith(".nc4"): continue
        if is_cmr and host != "data.gesdisc.earthdata.nasa.gov": continue
        low = href.lower()
        if any(marker in low for marker in ("s3.", "opendap", "/metadata", "/documentation", ".html")): continue
        priority = 0 if rel.endswith("/data#") or rel.endswith("#getdata") else 1
        candidates.append((priority, href))
    return [href for _, href in sorted(candidates)]


def _classify_html(url: str, response: requests.Response) -> str:
    host = urlparse(url).hostname or ""
    if "earthdata" in host or "login" in str(getattr(response, "url", "")).lower(): return "Earthdata Login HTML"
    if "gesdisc" in host: return "GES DISC HTML error page"
    return "unexpected HTML response"


def _download_session() -> requests.Session:
    """Reuse earthaccess' authenticated HTTPS session when available."""
    try:
        return _earthaccess().get_requests_https_session()
    except Exception:
        return requests.Session()


def _stream_download(url: str, target: Path) -> Path:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or (parsed.hostname or "").lower() not in TRUSTED_DOWNLOAD_HOSTS or not parsed.path.lower().endswith(".nc4"):
        raise ValueError("invalid IMERG HTTPS .nc4 download URL")
    token = os.getenv("EARTHDATA_TOKEN"); current = url; history: list[str] = []; visited = {current}; session = _download_session()
    for attempt in range(10):
        host = (urlparse(current).hostname or "").lower()
        headers = {"Authorization": f"Bearer {token}"} if token and host in TRUSTED_DOWNLOAD_HOSTS else {}
        response = session.get(current, headers=headers, timeout=60, stream=True, allow_redirects=False)
        status = response.status_code; content_type = response.headers.get("Content-Type", "").lower()
        history.append(f"{host}:{status}")
        LOGGER.info("IMERG download response host=%s status=%s content_type=%s", host, status, content_type)
        if 300 <= status < 400 and response.headers.get("Location"):
            location = response.headers["Location"]
            next_url = requests.compat.urljoin(current, location); next_host = (urlparse(next_url).hostname or "").lower()
            LOGGER.info("IMERG download redirect %s -> %s", host, next_host)
            if next_host not in TRUSTED_DOWNLOAD_HOSTS: response.close(); raise RuntimeError(f"redirect to untrusted host {next_host}; chain={history}")
            if next_url in visited: response.close(); raise RuntimeError(f"redirect loop detected; chain={history}")
            visited.add(next_url)
            response.close(); current = next_url
            continue
        break
    try:
        response.raise_for_status()
        if "text/html" in content_type or "text/plain" in content_type:
            raise RuntimeError(f"{_classify_html(current, response)}; chain={history}")
        written = 0
        with target.open("wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output.write(chunk); written += len(chunk)
        if written == 0: raise RuntimeError("empty download")
        return target
    finally:
        response.close()


def _official_stream_download(url: str, target: Path) -> Path:
    """Download with Earthaccess session, isolating the unauthenticated CDN hop."""
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or (parsed.hostname or "").lower() not in TRUSTED_DOWNLOAD_HOSTS or not parsed.path.lower().endswith(".nc4"):
        raise ValueError("invalid IMERG HTTPS .nc4 download URL")
    auth_session = _download_session(); current = url; visited = {current}; chain = []; response = None
    for _ in range(10):
        host = (urlparse(current).hostname or "").lower()
        if host.endswith(".cloudfront.net"):
            # A CDN URL must never inherit Earthdata auth state.
            session = requests.Session(); kwargs = {"headers": {}, "allow_redirects": False}
        else:
            session = auth_session; kwargs = {"allow_redirects": False}
        response = session.get(current, timeout=60, stream=True, **kwargs)
        chain.append(f"{host}:{response.status_code}")
        LOGGER.info("IMERG official download response host=%s status=%s content_type=%s", host, response.status_code, response.headers.get("Content-Type", ""))
        location = response.headers.get("Location")
        if not (300 <= response.status_code < 400 and location): break
        next_url = requests.compat.urljoin(current, location); next_parts = urlparse(next_url); next_host = (next_parts.hostname or "").lower()
        if next_parts.scheme.lower() != "https" or not next_host or next_parts.username or next_parts.password:
            response.close(); raise RuntimeError(f"unsafe redirect; chain={chain}")
        cdn = next_host.endswith(".cloudfront.net") and next_host != "cloudfront.net"
        allowed = next_host in TRUSTED_DOWNLOAD_HOSTS or (cdn and host in TRUSTED_DOWNLOAD_HOSTS)
        if not allowed: response.close(); raise RuntimeError(f"redirect to untrusted host {next_host}; chain={chain}")
        if next_url in visited: response.close(); raise RuntimeError(f"redirect loop detected; chain={chain}")
        visited.add(next_url); response.close(); current = next_url
    else:
        raise RuntimeError(f"redirect limit exceeded; chain={chain}")
    if response is None: raise RuntimeError("download did not return a response")
    try:
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" in content_type or "text/plain" in content_type:
            raise RuntimeError(f"{_classify_html(getattr(response, 'url', url), response)}; chain={chain}")
        with target.open("wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk: output.write(chunk)
        if not _valid_download(target):
            target.unlink(missing_ok=True); raise RuntimeError("downloaded response is not a valid NetCDF4/HDF5 file")
        return target
    finally:
        response.close()


def _valid_download(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0: return False
    with path.open("rb") as source: prefix = source.read(256).lstrip().lower()
    if prefix.startswith((b"<!doctype html", b"<html", b"<head")): return False
    if path.suffix.lower() in {".nc4", ".h5", ".hdf5"}:
        with path.open("rb") as source: return source.read(8) == b"\x89HDF\r\n\x1a\n"
    return True


def download_granules(granules: Iterable[Any], raw_dir: Path, earthaccess_module: Any | None = None) -> list[Path]:
    raw_dir.mkdir(parents=True, exist_ok=True); ea = earthaccess_module or _earthaccess(); files: list[Path] = []
    for granule in granules:
        granule_id = _granule_id(granule); links = _download_links(granule)
        if not links and not isinstance(granule, dict): links = [x for x in [_granule_path(granule)] if x.startswith("https://")]
        if not links: raise RuntimeError(f"IMERG download failed for {granule_id}: no HTTPS data link")
        selected = urlparse(links[0]); filename = selected.path.rsplit("/", 1)[-1]
        if selected.scheme.lower() != "https" or not selected.hostname or not filename.lower().endswith(".nc4"):
            raise RuntimeError(f"IMERG download failed for {granule_id}: invalid download URL")
        LOGGER.info("IMERG selected download host=%s filename=%s", selected.hostname.lower(), filename)
        target = raw_dir / filename
        if target.exists() and _valid_download(target):
            LOGGER.info("Resuming/skipping existing granule %s (%d bytes)", granule_id, target.stat().st_size)
            files.append(target); continue
        try:
            LOGGER.info("Downloading granule %s to %s", granule_id, target)
            if isinstance(granule, dict):
                try:
                    from earthaccess.results import DataGranule
                    official_granule = DataGranule(granule)
                    downloaded = ea.download(official_granule, local_path=str(raw_dir))
                except Exception as exc:
                    raise RuntimeError(f"official Earthaccess download failed: {str(exc)[:200]}") from exc
            else:
                downloaded = ea.download(granule, local_path=str(raw_dir))
        except Exception as exc:
            raise RuntimeError(f"IMERG download failed for {granule_id}: {str(exc)[:200]}") from exc
        candidates = [Path(x) for x in downloaded] if isinstance(downloaded, (list, tuple)) else [Path(downloaded)]
        valid = [x for x in candidates if _valid_download(x)]
        if not valid: raise RuntimeError(f"IMERG download failed for {granule_id}: no non-empty file returned")
        files.extend(valid)
    return files


def _find_var(ds: Any) -> Any:
    for name in ("precipitation", "precipitationCal", "precipitationCalSurface", "precipitationUncal"):
        if name in ds: return ds[name]
    raise ValueError("No IMERG precipitation variable found")


def extract_file(path: str | Path, bbox: tuple[float, float, float, float] = DEFAULT_BBOX) -> pd.DataFrame:
    try:
        import xarray as xr
        with xr.open_dataset(path, engine=None) as ds:
            variable = _find_var(ds); attrs = dict(variable.attrs); units = str(attrs.get("units", ""))
            if units.lower() not in {"mm/day", "mm d-1", "mm day-1", "mm/hr", "mm h-1"}:
                raise ValueError(f"Unsupported or missing precipitation units: {units!r}")
            lat_name = next((x for x in ("lat", "latitude", "Latitude") if x in ds), None); lon_name = next((x for x in ("lon", "longitude", "Longitude") if x in ds), None)
            if not lat_name or not lon_name: raise ValueError("Dataset lacks latitude/longitude coordinates")
            da = variable
            if "time" not in da.dims:
                da = da.expand_dims(time=[pd.Timestamp(path.name[:8]) if path.name[:8].isdigit() else pd.Timestamp(date.today())])
            da = da.sel({lat_name: slice(bbox[1], bbox[3]), lon_name: slice(bbox[0], bbox[2])})
            frame = da.to_dataframe(name="precipitation").reset_index()
            frame = frame.rename(columns={lat_name: "latitude", lon_name: "longitude", "time": "date"})
            frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
            values = pd.to_numeric(frame["precipitation"], errors="coerce"); fill = attrs.get("_FillValue", attrs.get("missing_value", -9999.0)); frame["precipitation_mm_day"] = values.mask(values == fill)
            if units.lower() in {"mm/hr", "mm h-1"}: frame["precipitation_mm_day"] *= 24.0
            frame = frame.dropna(subset=["precipitation_mm_day"])[["date", "latitude", "longitude", "precipitation_mm_day"]]
            return frame
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Cannot extract IMERG file {path}: {exc}") from exc


def quality_report(frame: pd.DataFrame, files: list[Path], start: str, end: str, bbox: tuple[float, float, float, float], granules: int) -> dict[str, Any]:
    expected = pd.date_range(start, end, freq="D"); dates = pd.to_datetime(frame["date"]).dt.normalize() if not frame.empty else pd.Series(dtype="datetime64[ns]")
    return {"total_days": len(expected), "days_with_data": int(dates.nunique()), "days_missing": int(len(set(expected) - set(dates)),), "grid_cells": int(frame[["latitude", "longitude"]].drop_duplicates().shape[0]) if not frame.empty else 0, "duplicate_records": int(frame.duplicated(["date", "latitude", "longitude"]).sum()), "precipitation_mm_day": {"min": float(frame.precipitation_mm_day.min()) if not frame.empty else None, "max": float(frame.precipitation_mm_day.max()) if not frame.empty else None, "mean": float(frame.precipitation_mm_day.mean()) if not frame.empty else None}, "units": "mm/day", "conversion": "none (source mm/day) or x24 for source mm/hr", "collection": SHORT_NAME, "version": VERSION, "bbox": bbox, "start": start, "end": end, "granules": granules, "raw_files": [str(x) for x in files]}


def run(start: str, end: str, bbox: tuple[float, float, float, float], output_dir: Path, batch_size: int = 31, one_week: bool = False) -> pd.DataFrame:
    if one_week: end = min(end, (pd.Timestamp(start) + pd.Timedelta(days=6)).strftime("%Y-%m-%d"))
    login_earthdata(); granules = discover(start, end, bbox); raw_dir = output_dir / "raw" / "imerg"; files = download_granules(granules, raw_dir)
    frames = [extract_file(path, bbox) for path in files]; frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["date", "latitude", "longitude", "precipitation_mm_day"])
    frame["source"] = "NASA GPM IMERG Final Run"; frame["product_version"] = VERSION; frame = frame[CSV_COLUMNS].sort_values(["date", "latitude", "longitude"]).drop_duplicates(["date", "latitude", "longitude"])
    processed = output_dir / "processed" / "imerg"; processed.mkdir(parents=True, exist_ok=True); frame.to_csv(processed / "can_gio_precipitation_daily_2025.csv", index=False); (processed / "metadata.json").write_text(json.dumps(quality_report(frame, files, start, end, bbox, len(granules)), indent=2), encoding="utf-8"); return frame


def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument("--start", default="2025-01-01"); p.add_argument("--end", default="2025-12-31"); p.add_argument("--west", type=float, default=DEFAULT_BBOX[0]); p.add_argument("--south", type=float, default=DEFAULT_BBOX[1]); p.add_argument("--east", type=float, default=DEFAULT_BBOX[2]); p.add_argument("--north", type=float, default=DEFAULT_BBOX[3]); p.add_argument("--output-dir", type=Path, default=Path("data")); p.add_argument("--batch-size", type=int, default=31); p.add_argument("--one-week", action="store_true"); a=p.parse_args(); print(f"Wrote {len(run(a.start,a.end,(a.west,a.south,a.east,a.north),a.output_dir,a.batch_size,a.one_week))} records")
if __name__ == "__main__": main()
