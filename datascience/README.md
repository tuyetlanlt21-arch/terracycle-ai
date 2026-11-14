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
