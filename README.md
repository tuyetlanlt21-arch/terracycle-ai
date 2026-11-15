# TerraCycle AI

Climate-adaptive crop-rotation decision support for NASA Space Apps 2026 Field Shift.

- `datascience/`: NASA POWER, SoilGrids and ECOCROP adapters
- `backend/`: FastAPI farm, soil, climate and rotation contracts
- `frontend/`: React/Vite decision interface
- `data/reference/`: traceable catalog/rules, with unavailable sources explicitly labeled
- `docs/data-sources.md`: provenance and limitations

NASA POWER is historical context, not a 48-hour forecast. Soil salinity EC and irrigation-water EC remain farmer/local inputs. No scientific values are fabricated.

## Reproducible decision example

The authentic, point-specific NASA POWER daily export for the Long Xuyen pilot is packaged under `data/processed/power/long_xuyen_pilot/` (10.383333, 105.450000; 2020-01-01 through 2026-10-31; retrieved 2026-11-15). Its source URL and coverage metadata are in `climate_summary.json`; the daily series used for calculations is `nasa_power_daily.csv`. The backend uses this bundle only for matching pilot coordinates. Other coordinates require their own matching dataset or a successful NASA POWER fetch; the pilot data is never borrowed for another location.

For a deterministic test, submit a historical `2024-11-01` rice scenario at the pilot coordinates with soil pH `6.0`, soil salinity EC `1.0 dS/m`, irrigation-water EC `0.5 dS/m`, irrigation available, freshwater adequate, drainage available, and water control available. These FarmProfile values are **hypothetical test inputs**, not farm observations. With candidate `rice`, the API should return `PASS`. Change soil salinity EC to `4.0 dS/m` and it should return `FAIL` against the sourced rice limit. Irrigation-water EC in FAO's `0.7–3.0 dS/m` restriction band remains `UNKNOWN` until field-specific management evidence is supplied; above `3.0 dS/m` is classified as `FAIL` in the screening. Sources and reasons are returned with the assessment.

The `PASS` result demonstrates that the rules can evaluate a complete, in-scope historical scenario. It is not a future weather forecast or a claim about a real farm. A planting window extending beyond the available daily observations remains `UNKNOWN`.

## Frontend and backend environment

- Local frontend configuration: copy `frontend/.env.example` to `frontend/.env`.
- Local backend configuration: copy `backend/.env.example` to `backend/.env`.
- For a hosted frontend build, set `VITE_API_BASE_URL` to the backend's public HTTPS URL before building. Production does not fall back to localhost.
- Set backend `CORS_ORIGINS` to the exact frontend origin (scheme and host, plus port if used). Keep production values in the hosting platform's environment settings, not in the repository.

## CI and opt-in auto-merge

GitHub Actions runs the backend and data science tests and builds the frontend.
Before using the bot, a repository admin should configure `main` to require a
pull request and the GitHub Actions checks `backend` and `frontend`. Enable
strict status checks (require the branch to be up to date), keep any existing
review requirements, and enable **Allow auto-merge** in repository settings.

Create the `automerge` label and apply it to a ready, same-repository PR
targeting `main` while CI or a required review is pending. The workflow
requests GitHub's native squash auto-merge. If the PR is already eligible to
merge immediately, use GitHub's regular merge control. To cancel an existing
request, use **Disable auto-merge** on the PR. Removing the label alone does
not cancel a request already registered with GitHub.
