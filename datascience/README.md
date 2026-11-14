# Data science module (Tuyết Lan)

This module contains NASA POWER CSV normalization, with unit/missing-value handling to be extended after verifying downloaded file metadata. It does NOT yet contain an empirically calibrated evaporation or salt-loss model.

1. Download NASA POWER daily time series with explicit coordinates, dates and parameters.
2. Record URL, coordinates, timespan, units, missing values, retrieval date.
3. Parse with `parse_power_daily_csv` and publish a reviewed dataset to `shared/fixtures`.
4. Connect the reviewed climate dataset to the BE endpoint; **do not replace the placeholder without source verification**.

Reference: https://power.larc.nasa.gov/
