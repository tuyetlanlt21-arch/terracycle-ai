import pandas as pd
import pytest
from datascience import integrate


def _frames():
    dates = ["2025-01-01", "2025-01-02"]
    power = pd.DataFrame({"date": dates, "latitude": [10.41]*2, "longitude": [106.96]*2, "temperature_avg_c": [25, 26], "temperature_max_c": [27, 28], "temperature_min_c": [23, 24], "precipitation_mm_day": [.1, .2], "relative_humidity_pct": [80, 81], "solar_radiation_kwh_m2_day": [13, 14]})
    imerg = pd.DataFrame({"date": [dates[0], dates[0], dates[1]], "latitude": [10.25, 10.35, 10.25], "longitude": [106.75, 106.75, 106.75], "precipitation_mm_day": [2., 4., 1.], "source": ["NASA"]*3, "product_version": ["07"]*3})
    gldas = pd.DataFrame({"date": dates, "latitude": [10.5]*2, "longitude": [107.0]*2, "evap_mm_day": [2, 3], "precipitation_mm_day": [.5, .6], "temperature_c": [25, 26], "specific_humidity_kg_kg": [.01, .02], "wind_m_s": [1, 1], "shortwave_w_m2": [100, 100], "longwave_w_m2": [400, 400], "source": ["NASA"]*2, "product_version": ["2.1"]*2, "quality_flag": ["valid"]*2})
    return power, imerg, gldas


def test_merge_keeps_rain_sources_separate_and_aggregates_imerg():
    result, report = integrate.integrate(*_frames(), "2025-01-01", "2025-01-02")
    assert list(result["date"]) == ["2025-01-01", "2025-01-02"]
    assert result.loc[0, "precipitation_imerg_mm_day"] == 3
    assert result.loc[0, "precipitation_gldas_mm_day"] == .5
    assert result.loc[0, "precipitation_power_mm_day"] == .1
    assert report["valid"] and report["duplicate_dates"] == 0


def test_missing_date_is_reported_and_not_imputed():
    power, imerg, gldas = _frames()
    result, report = integrate.integrate(power.iloc[:1], imerg.iloc[:1], gldas.iloc[:1], "2025-01-01", "2025-01-02")
    assert len(result) == 1 and report["missing_days"] == ["2025-01-02"]


def test_duplicate_power_dates_rejected():
    power, imerg, gldas = _frames()
    with pytest.raises(ValueError, match="duplicate dates"):
        integrate._validate(pd.concat([power, power.iloc[[0]]]), "POWER")


def test_invalid_precipitation_rejected():
    power, imerg, gldas = _frames(); imerg.loc[0, "precipitation_mm_day"] = -1
    with pytest.raises(ValueError, match="negative precipitation"):
        integrate._validate(imerg, "IMERG")

def test_grid_cell_count_uses_coordinate_pairs_not_cartesian_product():
    power, imerg, gldas = _frames()
    imerg = imerg.iloc[[0, 1]].copy()
    imerg.loc[1, "latitude"] = 10.35
    imerg.loc[1, "longitude"] = 106.85
    result, _ = integrate.integrate(power.iloc[:1], imerg, gldas.iloc[:1], "2025-01-01", "2025-01-01")
    assert result.loc[0, "imerg_grid_cells"] == 2
