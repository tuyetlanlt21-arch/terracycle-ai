"""FAO-56 reference and crop evapotranspiration calculations.

The implementation intentionally requires the meteorological inputs needed by
FAO-56 Penman-Monteith. It never substitutes temperature, humidity, radiation,
wind, or effective-rainfall assumptions when those observations are absent.
"""
from __future__ import annotations
import math
from typing import Any
import pandas as pd

FAO56_SOURCE = "https://www.fao.org/4/x0490e/x0490e00.htm"

def _missing(frame: pd.DataFrame, names: list[str]) -> list[str]:
    return [name for name in names if name not in frame or frame[name].isna().any()]

def reference_et0_fao56(frame: pd.DataFrame, latitude_deg: float, elevation_m: float = 0.0) -> dict[str, Any]:
    """Calculate daily FAO-56 PM ET0 in mm/day.

    NASA POWER must provide Tmin, Tmax, RH, solar radiation and wind speed.
    Solar radiation is converted from NASA POWER kWh m-2 day-1 to MJ m-2 day-1.
    """
    required = ["temperature_min_c", "temperature_max_c", "relative_humidity_pct", "solar_radiation_kwh_m2_day", "wind_speed_m_s", "surface_pressure_kpa"]
    missing = _missing(frame, required)
    if missing:
        return {"status": "UNKNOWN", "reason": "FAO-56 requires complete daily inputs: " + ", ".join(missing), "source": FAO56_SOURCE, "et0_mm": None}
    if not -90 <= latitude_deg <= 90:
        return {"status": "UNKNOWN", "reason": "latitude is outside FAO-56 bounds", "source": FAO56_SOURCE, "et0_mm": None}
    lat = math.radians(latitude_deg); values = []
    for _, row in frame.iterrows():
        date = pd.Timestamp(row["date"]); doy = int(date.dayofyear)
        tmin, tmax = float(row.temperature_min_c), float(row.temperature_max_c); tmean = (tmin + tmax) / 2
        rh = float(row.relative_humidity_pct); rs = float(row.solar_radiation_kwh_m2_day) * 3.6; u2 = float(row.wind_speed_m_s)
        delta = 4098 * (0.6108 * math.exp(17.27 * tmean / (tmean + 237.3))) / ((tmean + 237.3) ** 2)
        pressure = float(row.surface_pressure_kpa) * 10; gamma = 0.000665 * pressure
        es_tmin = 0.6108 * math.exp(17.27 * tmin / (tmin + 237.3)); es_tmax = 0.6108 * math.exp(17.27 * tmax / (tmax + 237.3)); es = (es_tmin + es_tmax) / 2; ea = es_tmin * rh / 100
        dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365); solar_declination = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39); sunset = math.acos(max(-1, min(1, -math.tan(lat) * math.tan(solar_declination))))
        ra = 24 * 60 / math.pi * 0.0820 * dr * (sunset * math.sin(lat) * math.sin(solar_declination) + math.cos(lat) * math.cos(solar_declination) * math.sin(sunset)); rso = (0.75 + 2e-5 * elevation_m) * ra
        rns = (1 - 0.23) * rs; rnl = 4.903e-9 * (((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2) * (0.34 - 0.14 * math.sqrt(max(ea, 0))) * (1.35 * min(rs / rso, 1) - 0.35) if rso else 0
        rn = rns - rnl; et0 = (0.408 * delta * rn + gamma * (900 / (tmean + 273)) * u2 * (es - ea)) / (delta + gamma * (1 + 0.34 * u2))
        values.append(max(0.0, et0))
    return {"status": "PASS", "source": FAO56_SOURCE, "et0_mm": values, "et0_total_mm": float(sum(values)), "observation_count": len(values), "units": "mm/day and mm"}

def effective_rainfall_scs(frame: pd.DataFrame) -> float | None:
    """Estimate effective rainfall with the monthly USDA-SCS method.

    This is a planning estimate, not field infiltration or paddy water balance.
    """
    if "date" not in frame or "precipitation_mm_day" not in frame or frame["precipitation_mm_day"].isna().any(): return None
    f=frame.copy(); f["month"]=pd.to_datetime(f["date"]).dt.to_period("M")
    total=0.0
    for value in f.groupby("month")["precipitation_mm_day"].sum(): total += value * (1 - 0.2 * value / 125) if value <= 250 else 125 + 0.1 * value
    return float(total)

def crop_et_and_irrigation(et0: dict[str, Any], crop_coefficients: dict[str, float] | None, rainfall_mm: float | None, effective_rainfall_mm: float | None = None) -> dict[str, Any]:
    """Calculate ETc and an upper-bound irrigation deficit.

    Rainfall is reported separately; no effective-rainfall fraction is assumed.
    """
    if et0.get("status") != "PASS": return {"status": "UNKNOWN", "reason": et0.get("reason", "ET0 unavailable"), "etc_total_mm": None, "irrigation_deficit_mm": None}
    if not crop_coefficients or crop_coefficients.get("kc_mean") is None: return {"status": "UNKNOWN", "reason": "verified crop coefficient is unavailable", "etc_total_mm": None, "irrigation_deficit_mm": None}
    if crop_coefficients.get("stages"):
        kc_values=[]
        for stage in crop_coefficients["stages"]:
            kc_values.extend([float(stage["kc"])] * int(stage["days"]))
        daily_et0=et0.get("et0_mm",[])
        if len(kc_values) < len(daily_et0): kc_values.extend([float(crop_coefficients.get("kc_mean",0))] * (len(daily_et0)-len(kc_values)))
        etc = float(sum(value * kc_values[index] for index,value in enumerate(daily_et0)))
        calculation="stage-weighted FAO-56 Kc"
    else:
        etc = float(et0["et0_total_mm"]) * float(crop_coefficients["kc_mean"]); calculation="mean Kc"
    effective = effective_rainfall_mm if effective_rainfall_mm is not None else None; deficit = None if effective is None else max(0.0, etc - effective)
    return {"status": "PASS" if deficit is not None else "UNKNOWN", "et0_total_mm": float(et0["et0_total_mm"]), "etc_total_mm": etc, "rainfall_total_mm": rainfall_mm, "effective_rainfall_mm": effective, "irrigation_deficit_mm": deficit, "kc_calculation": calculation, "rainfall_note": "USDA-SCS effective rainfall estimate; not a field infiltration or paddy-water model", "source": crop_coefficients.get("source", FAO56_SOURCE)}
