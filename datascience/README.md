# Data science pipelines

Run NASA POWER from repository root:

```powershell
python -m datascience.power --latitude 10.41 --longitude 106.96 --start 20250101 --end 20251231
```

Outputs are `data/processed/power/nasa_power_daily.csv`, `climate_monthly.csv` and `climate_summary.json`. The pipeline preserves the existing daily POWER CSV as a verified input and adds T2M, T2M_MAX, PRECTOTCORR, RH2M, ALLSKY_SFC_SW_DWN and WS2M validation, monthly metrics, seasons, missing counts and provenance.

SoilGrids is an optional, fail-safe adapter:

```powershell
python -m datascience.soilgrids --latitude 10.41 --longitude 106.96
```

The ECOCROP adapter normalizes a traceable CSV export when supplied; absent exports produce an explicitly unavailable catalog.

## Reproducibility and scientific guardrails

`power.py` requests exactly T2M, T2M_MAX, PRECTOTCORR, RH2M, ALLSKY_SFC_SW_DWN and WS2M. Requests are validated for coordinates and date order, NASA fill values (`-999`/`-9999`) become null, and failed requests are retried. When `run()` is used, the raw JSON is preserved as `raw_response.json` and a parameter-hash cache is written under `.cache`; cached responses are never treated as forecasts.

Monthly precipitation is the sum of daily precipitation. Temperature, humidity, radiation and wind are monthly means. Seasonal features are derived observations: dry months are defined as monthly precipitation below 100 mm and heat-stress months as monthly mean daily maximum temperature at least 35 C. These are screening indicators, not physiological or future-weather predictions.

The rotation engine uses the daily dataset only for `planting_date` through the sourced growth duration. Annual ECOCROP rainfall ranges are context and are never compared with a seasonal total. Precipitation is not evapotranspiration or irrigation demand. A missing planting window, soil EC, water requirement or field water balance remains `UNKNOWN`, with a null score. A sourced salinity limit is a hard failure only when the farmer-provided EC reaches that limit; SoilGrids null responses are never imputed.

Run deterministic checks from the repository root:

```powershell
$env:PYTHONPATH='backend'; python -m pytest -q datascience/tests backend/tests -p no:cacheprovider
python -m compileall -q datascience backend
```
