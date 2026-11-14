# TerraCycle AI

Climate-adaptive crop-rotation decision support for NASA Space Apps 2026 Field Shift.

- `datascience/`: NASA POWER, SoilGrids and ECOCROP adapters
- `backend/`: FastAPI farm, soil, climate and rotation contracts
- `frontend/`: React/Vite decision interface
- `data/reference/`: traceable catalog/rules, with unavailable sources explicitly labeled
- `docs/data-sources.md`: provenance and limitations

NASA POWER is historical context, not a 48-hour forecast. Soil salinity EC and irrigation-water EC remain farmer/local inputs. No scientific values are fabricated.

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
