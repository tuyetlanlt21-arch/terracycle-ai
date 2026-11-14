"""Integrate NASA POWER, GPM IMERG and GLDAS daily features.

The rainfall series remain separate: IMERG is satellite precipitation while
GLDAS is a land-surface-model precipitation rate. No missing values are
imputed and all dates are treated as UTC calendar dates.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

POWER_COLUMNS = ["date", "latitude", "longitude", "temperature_avg_c", "temperature_max_c", "temperature_min_c", "precipitation_mm_day", "relative_humidity_pct", "solar_radiation_kwh_m2_day"]
IMERG_COLUMNS = ["date", "latitude", "longitude", "precipitation_mm_day", "source", "product_version"]
GLDAS_COLUMNS = ["date", "latitude", "longitude", "evap_mm_day", "precipitation_mm_day", "temperature_c", "specific_humidity_kg_kg", "wind_m_s", "shortwave_w_m2", "longwave_w_m2", "source", "product_version", "quality_flag"]
OUTPUT_COLUMNS = ["date", "latitude_power", "longitude_power", "temperature_avg_c", "temperature_max_c", "temperature_min_c", "relative_humidity_pct", "solar_radiation_kwh_m2_day", "precipitation_power_mm_day", "precipitation_imerg_mm_day", "imerg_grid_cells", "latitude_gldas", "longitude_gldas", "evapotranspiration_gldas_mm_day", "precipitation_gldas_mm_day", "temperature_gldas_c", "specific_humidity_gldas_kg_kg", "wind_gldas_m_s", "shortwave_gldas_w_m2", "longwave_gldas_w_m2"]


def _read(path: Path, expected: list[str], name: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = [column for column in expected if column not in frame.columns]
    if missing:
        raise ValueError(f"{name} missing columns: {missing}")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise", utc=True).dt.strftime("%Y-%m-%d")
    if frame["date"].duplicated().any() and name in {"POWER", "GLDAS"}:
        raise ValueError(f"{name} has duplicate dates")
    return frame


def _validate(frame: pd.DataFrame, name: str) -> None:
    if name in {"POWER", "GLDAS"} and frame["date"].duplicated().any():
        raise ValueError(f"{name} has duplicate dates")
    numeric = frame.select_dtypes(include=[np.number])
    if numeric.isna().any().any():
        raise ValueError(f"{name} contains null numeric values")
    if not np.isfinite(numeric.to_numpy()).all():
        raise ValueError(f"{name} contains non-finite values")
    if name == "POWER":
        if not frame["relative_humidity_pct"].between(0, 100).all() or (frame[["precipitation_mm_day", "solar_radiation_kwh_m2_day"]] < 0).any().any():
            raise ValueError("POWER contains invalid range values")
    if name in {"IMERG", "GLDAS"} and (frame["precipitation_mm_day"] < 0).any():
        raise ValueError(f"{name} contains negative precipitation")


def normalize_sources(power_path: Path, imerg_path: Path, gldas_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    power = _read(power_path, POWER_COLUMNS, "POWER")
    imerg = _read(imerg_path, IMERG_COLUMNS, "IMERG")
    gldas = _read(gldas_path, GLDAS_COLUMNS, "GLDAS")
    _validate(power, "POWER"); _validate(imerg, "IMERG"); _validate(gldas, "GLDAS")
    return power, imerg, gldas


def integrate(power: pd.DataFrame, imerg: pd.DataFrame, gldas: pd.DataFrame, start: str, end: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    expected = pd.date_range(start, end, freq="D", tz="UTC").strftime("%Y-%m-%d")
    imerg_daily = imerg.groupby("date", as_index=False).agg(precipitation_imerg_mm_day=("precipitation_mm_day", "mean"))
    cell_counts = imerg.groupby("date").apply(lambda group: group[["latitude", "longitude"]].drop_duplicates().shape[0], include_groups=False)
    imerg_daily["imerg_grid_cells"] = imerg_daily["date"].map(cell_counts).astype("int64")
    p = power.rename(columns={"latitude": "latitude_power", "longitude": "longitude_power", "precipitation_mm_day": "precipitation_power_mm_day"})
    g = gldas.rename(columns={"latitude": "latitude_gldas", "longitude": "longitude_gldas", "evap_mm_day": "evapotranspiration_gldas_mm_day", "precipitation_mm_day": "precipitation_gldas_mm_day", "temperature_c": "temperature_gldas_c", "specific_humidity_kg_kg": "specific_humidity_gldas_kg_kg", "wind_m_s": "wind_gldas_m_s", "shortwave_w_m2": "shortwave_gldas_w_m2", "longwave_w_m2": "longwave_gldas_w_m2"})
    g_columns = ["date", "latitude_gldas", "longitude_gldas", "evapotranspiration_gldas_mm_day", "precipitation_gldas_mm_day", "temperature_gldas_c", "specific_humidity_gldas_kg_kg", "wind_gldas_m_s", "shortwave_gldas_w_m2", "longwave_gldas_w_m2"]
    result = p.merge(imerg_daily, on="date", how="inner").merge(g[g_columns], on="date", how="inner")
    result = result[(result.date >= start) & (result.date <= end)].sort_values("date").reset_index(drop=True)
    result = result[OUTPUT_COLUMNS]
    missing = sorted(set(expected) - set(result["date"]))
    report = {"sources": {"power": str(power_path if False else "NASA POWER"), "imerg": "NASA GPM IMERG Final Run V07", "gldas": "NASA GLDAS Noah LSM V2.1"}, "start": start, "end": end, "timezone": "UTC", "expected_days": len(expected), "days_with_all_sources": len(result), "missing_days": missing, "duplicate_dates": int(result["date"].duplicated().sum()), "null_values": result.isna().sum().to_dict(), "valid": bool(not missing and result["date"].is_unique and not result.isna().any().any()), "transformations": {"IMERG": "mean of source grid cells per UTC day; no unit conversion (mm/day)", "GLDAS": "preserved daily spatial mean and source conversion", "POWER": "preserved daily point values"}, "warnings": ["IMERG and GLDAS precipitation are separate source variables and must not be summed.", "IMERG is 0.1-degree grid; GLDAS is 0.25-degree grid; POWER is a point value.", "No missing-value imputation or interpolation was applied."]}
    return result, report


def run(start: str, end: str, output_dir: Path, power_path: Path, imerg_path: Path, gldas_path: Path) -> pd.DataFrame:
    power, imerg, gldas = normalize_sources(power_path, imerg_path, gldas_path)
    result, report = integrate(power, imerg, gldas, start, end)
    if not report["valid"]: raise ValueError(f"Integration quality validation failed: {report['missing_days']}")
    out = output_dir / "processed" / "integrated"; out.mkdir(parents=True, exist_ok=True)
    result.to_csv(out / "saltshift_daily_features.csv", index=False)
    (out / "integration_quality_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Integrate NASA daily features for SaltShift")
    parser.add_argument("--start", default="2025-01-01"); parser.add_argument("--end", default="2025-01-07"); parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--power", type=Path, default=Path("data/processed/power/can_gio_daily_2025.csv")); parser.add_argument("--imerg", type=Path, default=Path("data/processed/imerg/can_gio_precipitation_daily_2025.csv")); parser.add_argument("--gldas", type=Path, default=Path("data/processed/gldas/gldas_daily_2025.csv"))
    args = parser.parse_args(); result = run(args.start, args.end, args.output_dir, args.power, args.imerg, args.gldas); print(f"Wrote {len(result)} integrated rows")


if __name__ == "__main__": main()
