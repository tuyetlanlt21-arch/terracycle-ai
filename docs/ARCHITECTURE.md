# TerraCycle AI architecture

The product compares current practice, water saving and soil recovery strategies for a farmer-entered farm profile. Historical NASA POWER climate features provide context; they are never presented as a forecast. SoilGrids supplies modeled soil properties only, while salinity EC fields remain farmer/local measurements.

API: `GET /api/climate/summary`, `GET /api/crops`, `GET /api/soil/profile`, `POST /api/rotations/compare`.
