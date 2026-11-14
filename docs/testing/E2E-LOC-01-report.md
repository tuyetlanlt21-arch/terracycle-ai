# E2E-LOC-01 — Location-aware integration report

Date: 2026-11-14

## Scope

Validated the Backend, DS adapters and Frontend contract for Long Xuyên
(`10.383333, 105.45`) and Cần Giờ (`10.72, 106.7`) using the same valid
`FarmProfile`. Backend was started with `PYTHONPATH=backend;.` and
`LOCATION_DATA_FETCH_ENABLED=1`.

## Results

| Check | Result | Evidence |
|---|---|---|
| Backend startup | PASS | Uvicorn started and `/api/rotations/compare` returned 200 for both points |
| Long Xuyên NASA POWER | PASS | Response URL and evaluated location contained `10.383333,105.45`; period `20200101–20251231`; daily climate window evaluated |
| Long Xuyên rules | PASS | `rotation_rules.json@1.0.0`, `verified_point_only`, no applicability warning |
| Long Xuyên SoilGrids | PASS/NO_DATA | Location matched; stored response contained null pixel means and was not imputed. Availability was corrected to `no_data`. |
| Cần Giờ cache isolation | PASS | No Long Xuyên artifact was reused; response location was `10.72,106.7` |
| Cần Giờ live NASA POWER | BLOCKED | Environment proxy refused connection to `127.0.0.1:9`; service returned unavailable/UNKNOWN rather than fabricating values |
| Cần Giờ rule guard | PASS | Calendar and transition were `UNKNOWN`; eligibility was `UNKNOWN`, never an unsupported PASS |
| Provenance | PASS | Location, availability, period, observation date, rule set, scope, applicability reason and warnings propagated in API response |
| Frontend build | PASS | `tsc -b && vite build`; 1581 modules transformed |
| Backend + DS tests | PASS | `125 passed, 2 warnings` |

## Bugs fixed

1. Location integration reported a SoilGrids profile with all-null values as
   `available`. It now reports `no_data`; only a loaded profile is available.
2. `_window()` used a default argument bound to the original daily dataset,
   defeating test monkeypatching and potentially obscuring location-specific
   paths. It now resolves `DAILY` at call time.
3. Pydantic response models were made compatible with existing DS contract
   tests that access suitability, provenance and scoring metadata as mappings.
4. The old exact provenance test was updated to assert the legacy fields are a
   subset, allowing the location-aware fields required by BE-LOC-02.
5. Added repository-local pytest temporary-directory configuration in
   `conftest.py` and ignored `**/*.tsbuildinfo` in `.gitignore`.
6. Frontend manual coordinate input now emits partial coordinate updates,
   preventing an unfinished latitude/longitude edit from overwriting the
   other coordinate with zero.

## Test commands

```powershell
$env:PYTHONPATH='backend;.'
python -m pytest datascience/tests backend/tests -q -p no:cacheprovider
# 125 passed, 2 warnings

cd frontend
npm run build
# PASS
```

## Demo decision

- Long Xuyên: **GO with explicit SoilGrids no-data disclosure**. NASA POWER
  and pilot rules are location-consistent; soil nulls remain unresolved.
- Cần Giờ: **NO-GO for a scientific rotation recommendation**. The system is
  safe for demonstrating location capture, live-data failure handling and
  provenance, but no region-verified calendar/transition rule set exists and
  the live NASA request was blocked by the current proxy environment.

## Remaining limitations

- Live Cần Giờ verification requires outbound access to NASA POWER and
  SoilGrids or a separately provisioned, coordinate-matched cache.
- The current rule set is verified only at the Long Xuyên pilot point.
- SoilGrids predictions do not supply farmer soil salinity EC or irrigation
  water EC, and null values are intentionally not filled.
- Frontend globe/GPS interaction is covered by the build and shared event
  contract, but browser permission and canvas interaction require a real
  browser automation environment for full click-level E2E coverage.
