# TerraCycle AI

Climate-adaptive crop-rotation decision support for NASA Space Apps 2026 Field Shift.

- `datascience/`: NASA POWER, SoilGrids and ECOCROP adapters
- `backend/`: FastAPI farm, soil, climate and rotation contracts
- `frontend/`: React/Vite decision interface
- `data/reference/`: traceable catalog/rules, with unavailable sources explicitly labeled
- `docs/data-sources.md`: provenance and limitations

NASA POWER is historical context, not a 48-hour forecast. Soil salinity EC and irrigation-water EC remain farmer/local inputs. No scientific values are fabricated.
