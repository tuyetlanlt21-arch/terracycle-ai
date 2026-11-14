# NASA POWER data acquisition

`datascience/power.py` calls the official NASA POWER daily point API, preserves raw JSON, normalizes `properties.parameter` into CSV, and writes metadata plus quality checks.

Run from repository root:

```powershell
python -m datascience.power
```

Outputs: `data/raw/power/can_gio_2025.json`, `data/processed/power/can_gio_daily_2025.csv`, and `data/processed/power/metadata.json`.

Coordinates, dates, and paths are configurable, e.g. `python -m datascience.power --latitude 10.41 --longitude 106.96 --start 20250101 --end 20251231`.

The client uses a 30-second timeout and three attempts with exponential backoff. It rejects malformed responses, unexpected temperature units, invalid humidity, negative precipitation/solar values, and does not impute missing values. NASA fill values `-999` and `-9999` become null.

Run tests with `python -m pytest -q datascience/tests --basetemp .pytest-tmp`.

The real NASA request was attempted in this environment but the configured proxy refused the connection. No real 2025 outputs are claimed as verified yet; tests validate normalization and quality logic using an API-shaped fixture.

## GPM IMERG Final Run (DS-02)

Install the data-science dependencies on Windows:

```powershell
python -m pip install -r datascience/requirements.txt
```

Authenticate through Earthaccess using its secure credential chain (Earthdata Login/netrc/environment or interactive login); credentials are never stored in source code. Then run a one-week smoke test:

```powershell
python -m datascience.imerg --start 2025-01-01 --end 2025-01-07 --one-week
```

Full-year run:

```powershell
python -m datascience.imerg --start 2025-01-01 --end 2025-12-31 --batch-size 31
```

The IMERG pipeline targets `GPM_3IMERGDF`, version `07`, filters the requested bounding box, preserves downloaded granules under `data/raw/imerg/`, and writes `data/processed/imerg/can_gio_precipitation_daily_2025.csv` plus `metadata.json`. It skips non-empty existing downloads, treats fill values as missing, never converts missing rainfall to zero, and reports missing days, cells, duplicates, ranges, units, collection, version, and raw files.

DS-02 tests use mocks for Earthaccess and optional NetCDF fixtures. Run them with `python -m pytest -q datascience/tests/test_imerg.py -p no:cacheprovider`; NetCDF tests are skipped until xarray is installed. DS-02 is `CODE COMPLETE` until a Windows environment with Earthdata credentials successfully discovers and downloads real granules.

The independent real-data smoke test is `python -m datascience.tests.smoke_imerg_download`. It uses CMR `granules.umm_json` discovery with `page_size=100`, converts each UMM item to the Earthaccess 0.19.0 `DataGranule({"umm": ...})` shape, and uses only `earthaccess.login()` and `earthaccess.download()` for one 2025-01-01 granule. It validates HDF5/NetCDF4 and the precipitation variable, and returns a non-zero result with a clear reason when credentials/network access are unavailable.

## GLDAS-2.1 Noah (DS-03)

The GLDAS pipeline targets NASA GES DISC `GLDAS_NOAH025_3H`, version `2.1`: NetCDF, 3-hourly, 0.25-degree. It uses CMR `granules.umm_json` discovery with `page_size=100`, Earthaccess authentication/download, xarray extraction, spatial mean over grid cells intersecting `[106.7, 10.2, 107.2, 10.7]`, and UTC daily aggregation.

Smoke test:

```powershell
python -m datascience.tests.smoke_gldas_download
```

Seven-day run:

```powershell
python -m datascience.gldas --start 2025-01-01 --end 2025-01-07
```

Full-year run:

```powershell
python -m datascience.gldas --start 2025-01-01 --end 2025-12-31
```

Water fluxes `Evap_tavg` and `Rainf_tavg` are rates in `kg m-2 s-1`; each 3-hour value is multiplied by 10800 seconds and daily values are summed. `Tair_f_inst` is converted K to degrees C; state/flux variables are averaged spatially and, where appropriate, temporally. GLDAS evaporation is a land-surface model estimate, not direct salt-pond evaporation and not a future weather forecast. Outputs are `data/raw/gldas/`, `data/processed/gldas/gldas_daily_2025.csv`, and `data/processed/gldas/gldas_quality_report.json`.

## NASA integration (DS-04)

The independent integration module reads the existing NASA POWER, IMERG and GLDAS CSVs, normalizes dates as UTC calendar dates, and inner-joins only days present and valid in all three sources. IMERG precipitation is spatially averaged across its source cells; GLDAS precipitation and evapotranspiration remain separate model variables; no rainfall series are added and no missing values are imputed.

Run the verified seven-day integration:

```powershell
python -m datascience.integrate --start 2025-01-01 --end 2025-01-07
```

Outputs are `data/processed/integrated/saltshift_daily_features.csv` and `data/processed/integrated/integration_quality_report.json`. Input paths can be overridden with `--power`, `--imerg`, and `--gldas`.

## Salt risk engine (DS-05)

Run a transparent historical MVP assessment from the integrated NASA features:

```powershell
python -m datascience.salt_risk --stage evaporation
```

The engine writes `data/processed/risk/salt_risk_assessment.csv` and `data/processed/risk/salt_risk_report.json`. Thresholds and weights are centralized in `datascience/salt_risk.py` and explicitly require validation by salt-production experts. The engine does not forecast, invent brine salinity, or impute missing data; incomplete rows receive `INSUFFICIENT_DATA`.
