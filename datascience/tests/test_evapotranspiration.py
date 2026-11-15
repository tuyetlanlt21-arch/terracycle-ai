import pandas as pd
from datascience.evapotranspiration import reference_et0_fao56, crop_et_and_irrigation

def test_fao56_requires_complete_observations():
    frame = pd.DataFrame({"date": ["2024-01-01"], "temperature_max_c": [30], "relative_humidity_pct": [70], "solar_radiation_kwh_m2_day": [18], "wind_speed_m_s": [2], "surface_pressure_kpa": [101]})
    result = reference_et0_fao56(frame, 10.38)
    assert result["status"] == "UNKNOWN" and "temperature_min_c" in result["reason"]

def test_fao56_and_crop_water_balance():
    frame = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=3), "temperature_min_c": [20,20,20], "temperature_max_c": [30,30,30], "relative_humidity_pct": [70,70,70], "solar_radiation_kwh_m2_day": [18,18,18], "wind_speed_m_s": [2,2,2], "surface_pressure_kpa": [101,101,101]})
    et0 = reference_et0_fao56(frame, 10.38)
    assert et0["status"] == "PASS" and et0["et0_total_mm"] > 0
    balance = crop_et_and_irrigation(et0, {"kc_mean": 1.0, "source": "FAO-56"}, 1.0, effective_rainfall_mm=1.0)
    assert balance["status"] == "PASS" and balance["irrigation_deficit_mm"] >= 0
