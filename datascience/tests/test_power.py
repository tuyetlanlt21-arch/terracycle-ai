import pandas as pd
from datascience.power import normalize, monthly_summary
def payload():
    values={p:{"20250101":1,"20250102":2} for p in ["T2M","T2M_MAX","PRECTOTCORR","RH2M","ALLSKY_SFC_SW_DWN","WS2M"]}; values["T2M"]["20250102"]=-999
    return {"properties":{"coordinates":{"latitude":10.4,"longitude":106.9},"parameter":values}}
def test_normalize_required_columns_and_missing():
    frame, quality=normalize(payload()); assert "wind_speed_m_s" in frame; assert pd.isna(frame.loc[1,"temperature_avg_c"]); assert quality["missing_count"]==1
def test_monthly_sum_mean():
    frame,_=normalize(payload()); summary=monthly_summary(frame); assert summary.loc[0,"precipitation_sum_mm"]==3; assert summary.loc[0,"temperature_mean_c"]==1
