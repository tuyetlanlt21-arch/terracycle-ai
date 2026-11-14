from datascience.power import parse_power_daily_csv

def test_csv(tmp_path):
    path = tmp_path / "power.csv"
    path.write_text("-BEGIN HEADER-\nexample\n-END HEADER-\nYEAR,MO,DY,PRECTOTCORR,T2M,RH2M,ALLSKY_SFC_SW_DWN,WS2M\n2025,1,2,0,30,75,5,2\n2025,1,3,-999,29,76,4,3\n", encoding="utf-8")
    rows = parse_power_daily_csv(path)
    assert len(rows) == 2
    assert rows[0]["date"] == "2025-01-02"
    assert rows[1]["PRECTOTCORR"] is None
