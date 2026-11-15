import pandas as pd
from datascience.power import normalize, monthly_summary, seasonal_features, seasonal_summary, historical_growing_period_rainfall, build_params, validate_daily_frame, extract_growth_window
def payload():
    values={p:{"20250101":1,"20250102":2} for p in ["T2M","T2M_MIN","T2M_MAX","PRECTOTCORR","RH2M","ALLSKY_SFC_SW_DWN","WS2M","PS"]}; values["T2M"]["20250102"]=-999
    return {"properties":{"coordinates":{"latitude":10.4,"longitude":106.9},"parameter":values}}
def test_normalize_required_columns_and_missing():
    frame, quality=normalize(payload()); assert "wind_speed_m_s" in frame; assert pd.isna(frame.loc[1,"temperature_avg_c"]); assert quality["missing_count"]==1
def test_monthly_sum_mean():
    frame,_=normalize(payload()); summary=monthly_summary(frame); assert summary.loc[0,"precipitation_sum_mm"]==3; assert summary.loc[0,"temperature_mean_c"]==1

def test_request_validation_and_derived_seasonal_indicators():
    assert build_params(10.4, 106.9, "20200101", "20201231")["parameters"].count(",") == 7
    monthly=monthly_summary(normalize(payload())[0])
    features=seasonal_features(monthly)
    assert features["indicators"]["climate_indicators_are_derived_observations"] is True
    assert "dry_month_count" in features["dry"]

def test_leap_year_coverage_and_cross_year_growth_window():
    frame=pd.DataFrame({"date":pd.date_range("2024-12-20","2025-01-10"),"temperature_avg_c":25.0,"temperature_max_c":32.0,"precipitation_mm_day":1.0,"relative_humidity_pct":80.0,"solar_radiation_kwh_m2_day":4.0,"wind_speed_m_s":2.0})
    quality=validate_daily_frame(frame,"20241220","20250110")
    assert quality["valid"] is True
    selected,window=extract_growth_window(frame,"2024-12-25",10)
    assert window["status"]=="PASS" and window["crosses_calendar_year"] is True
    assert len(selected)==10

def test_missing_date_is_not_converted_to_zero():
    frame=pd.DataFrame({"date":pd.to_datetime(["2024-01-01","2024-01-03"]),"temperature_avg_c":[25.0,25.0],"temperature_max_c":[32.0,32.0],"precipitation_mm_day":[1.0,1.0],"relative_humidity_pct":[80.0,80.0],"solar_radiation_kwh_m2_day":[4.0,4.0],"wind_speed_m_s":[2.0,2.0]})
    quality=validate_daily_frame(frame,"20240101","20240103")
    assert quality["valid"] is False and quality["missing_dates"] == ["2024-01-02"]

def test_seasonal_aggregation_preserves_rainfall_totals():
    dates = pd.date_range("2024-06-01", "2024-09-30")
    frame = pd.DataFrame({"date": dates, "precipitation_mm_day": 2.0})
    result = seasonal_summary(frame)
    wet = result[result["season"] == "wet"].iloc[0]
    assert wet["precipitation_sum_mm"] == len(dates) * 2
    assert wet["status"] == "PASS"

def test_cross_year_growing_period_and_historical_average():
    dates = pd.date_range("2022-12-20", "2025-01-10")
    frame = pd.DataFrame({"date": dates, "precipitation_mm_day": dates.year.astype(float) - 2020})
    result = historical_growing_period_rainfall(frame, "2022-12-25", 10)
    assert result["rainfall_total_mm"] == 23
    assert result["historical_average_mm"] == 33

def test_missing_growing_period_observation_is_unknown():
    dates = pd.date_range("2024-12-25", "2025-01-03").delete(3)
    frame = pd.DataFrame({"date": dates, "precipitation_mm_day": 1.0})
    result = historical_growing_period_rainfall(frame, "2024-12-25", 10)
    assert result["status"] == "UNKNOWN"
    assert "incomplete" in result["coverage"]["reason"]
