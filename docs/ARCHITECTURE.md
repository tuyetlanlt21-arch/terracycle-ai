# SaltShift architecture and team ownership

## Goal

Allow a salt farmer to compare interventions for 1–20 batches under a **user-entered** rain scenario. The service explains why an action was suggested. It makes **no** live 48-hour rain prediction or validated financial loss estimate.

## Modules

| Module | Owner | Responsibilities |
|---|---|---|
| Frontend | Tuyết Lan | Form, validation UX, report, error state |
| DS | Tuyết Lan | NASA POWER processing, evidence provenance, decision heuristics |
| Backend API | Nhật Trường | Pydantic contract, endpoints, response integration |
| Backend testing/deploy | Minh Thắng | Contract tests, integration, deploy/CORS |
| Requirements/pitch | Minh Khánh | Domain research, eligibility gate, acceptance criteria |

## API

`GET /health`: availability.
`GET /api/demo`: sample scenario.
`GET /api/climate/summary`: placeholder until independently validated NASA data is ingested.
`POST /api/scenarios/compare`: scenario → ranked per-field options.
`POST /api/salt-fields/analyze`: alias to comparison for the hackathon.

## Limitations & next steps

- Salt-making is **not crop rotation**: confirm challenge eligibility before coding challenge-specific features.
- NASA POWER records historical regional weather and cannot predict the next 48 hours.
- GPM rainfall does not independently establish flooding or salt concentration of each pond.
- The first ranking heuristic does **not** enforce a global worker/budget allocation. It assesses individual options only; build true constrained optimization before claiming optimal distribution.
- Protection efficacy, harvesting quality and loss figures need field validation.
- The frontend starter is a new app; preserve/port any separately completed cinematic landing page after review.
