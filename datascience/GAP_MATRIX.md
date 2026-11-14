# SaltShift Data Science gap matrix

| Area | Before | After | Evidence / limitation |
|---|---|---|---|
| POWER request and fill values | Implemented, but request validation was narrow | Coordinates/date order, required parameters, retries, cache, raw JSON and fill-value handling retained | No imputation; source is NASA POWER |
| Daily temporal quality | Partial | Request-period coverage, duplicate dates, leap-day and continuity validation added | Missing dates remain explicit |
| Monthly/seasonal features | Implemented | Existing aggregation retained; dry-month, heat-stress and variability definitions documented | Indicators are derived observations, not forecasts |
| Crop-specific climate window | Missing as reusable DS primitive | `assess_climate_window` and `extract_growth_window` added | Annual rainfall references remain context only |
| Cross-year seasons | Not explicitly tested | December-January extraction supported and tested | Requires daily coverage for the complete window |
| Crop catalog | Four sourced crops with explicit gaps | Existing values preserved; no unsupported values added | Mung-bean seasonal water and non-rice calendars remain UNKNOWN |
| Multi-season sequence validation | Individual-crop checks only | Chronology, overlap and transition validation added | No claim of optimality |
| Strategy evaluation | Backend-owned ranking existed | DS-only sourced ranking primitives added for current, water and soil strategies | Ranking does not override hard feasibility |
| Soil/salinity | SoilGrids no-values preserved | Farmer soil EC and irrigation-water EC remain separate evidence channels | No ET0, crop coefficients or field water balance |
| Provenance | Present in POWER/catalog | New DS outputs carry source/evidence references | No field-level validation claim |

## Scientific status

The DS layer is complete for an explainable screening MVP. It is not a calibrated agronomic optimizer: seasonal rainfall suitability, irrigation demand, SoilGrids coverage and some crop calendars remain explicitly unknown where verified evidence is unavailable.
