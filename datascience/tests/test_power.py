from datascience.power import parse_power_daily_csv, normalize

def test_csv():
    from pathlib import Path
    path = Path(__file__).with_name("_test_power.csv")
    try:
        path.write_text("-BEGIN HEADER-\nexample\n-END HEADER-\nYEAR,MO,DY,PRECTOTCORR,T2M,RH2M,ALLSKY_SFC_SW_DWN,WS2M\n2025,1,2,0,30,75,5,2\n2025,1,3,-999,29,76,4,3\n", encoding="utf-8")
        rows = parse_power_daily_csv(path)
        assert len(rows) == 2
        assert rows[0]["date"] == "2025-01-02"
        assert rows[1]["PRECTOTCORR"] is None
    finally:
        path.unlink(missing_ok=True)

def test_normalize_json_schema_and_quality():
    payload = {
        "header": {"units": {"T2M": "C", "T2M_MAX": "C", "T2M_MIN": "C", "PRECTOTCORR": "mm/day", "RH2M": "%", "ALLSKY_SFC_SW_DWN": "kW-hr/m^2/day"}},
        "properties": {"coordinates": {"latitude": 10.41, "longitude": 106.96}, "parameter": {
            "T2M": {"20250101": 27.1, "20250102": -999}, "T2M_MAX": {"20250101": 32, "20250102": 33}, "T2M_MIN": {"20250101": 23, "20250102": 24},
            "PRECTOTCORR": {"20250101": 0, "20250102": 1.2}, "RH2M": {"20250101": 80, "20250102": 81}, "ALLSKY_SFC_SW_DWN": {"20250101": 4.5, "20250102": 5}
        }}
    }
    frame, quality = normalize(payload)
    assert list(frame.columns) == ["date", "latitude", "longitude", "temperature_avg_c", "temperature_max_c", "temperature_min_c", "precipitation_mm_day", "relative_humidity_pct", "solar_radiation_kwh_m2_day"]
    assert len(frame) == 2 and frame.loc[1, "temperature_avg_c"] != frame.loc[1, "temperature_avg_c"]
    assert quality["units"]["T2M"] == "C" and quality["duplicate_dates"] == 0
