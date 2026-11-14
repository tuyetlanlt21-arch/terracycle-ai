from app.models import ActionOption, CompareResponse, ScenarioRequest

DISCLAIMER = "Heuristic demonstration only; no validated loss probability or yield prediction."


def compare_scenarios(request: ScenarioRequest) -> CompareResponse:
    # Deterministic rules, not a rainfall-to-loss model. Expected values are user estimates.
    options: list[tuple[float, ActionOption]] = []
    for field in request.fields:
        remaining_days = request.hours_until_rain / 24
        can_harvest = field.stage == "ready" and field.days_to_harvest <= remaining_days
        can_protect = field.protection_available and field.protection_cost_vnd <= request.available_budget_vnd and request.available_workers > 0
        if request.rain_mm == 0:
            action, cost, rationale, urgency = "continue", 0, ["No rain was entered for this scenario."], 0
        elif can_harvest:
            action, cost, rationale, urgency = "harvest_early", 0, ["Field is nearly ready and harvest timing fits the scenario.", "Verify crystal quality and actual labor capacity on site."], 3
        elif can_protect:
            action, cost, rationale, urgency = "protect", field.protection_cost_vnd, ["Protection materials, workers and budget are marked available.", "Check feasibility and effectiveness of protection in the actual field."], 2
        elif field.stage == "concentrating":
            action, cost, rationale, urgency = "postpone", 0, ["Early-stage concentration; consider pausing further investment.", "Do not assume water can be safely discharged without checking local practice."], 1
        else:
            action, cost, rationale, urgency = "continue", 0, ["No feasible harvest/protection option was supplied.", "Seek local expert advice; continuing does not imply the field is safe."], 1
        # Sorting is a transparent triage heuristic, not predicted avoided loss.
        score = urgency * 1_000_000_000 + field.expected_value_vnd
        options.append((score, ActionOption(action=action, field_id=field.id, priority=0, rationale=rationale, estimated_cost_vnd=cost, assumption=DISCLAIMER)))
    options.sort(key=lambda item: (-item[0], item[1].field_id))
    ranked = [entry.model_copy(update={"priority": index}) for index, (_, entry) in enumerate(options, start=1)]
    return CompareResponse(scenario={"rain_mm": request.rain_mm, "hours_until_rain": request.hours_until_rain}, actions=ranked, warnings=["The scenario is user supplied; historical NASA climate is not a short-term forecast.", "Each field is evaluated separately; the displayed priorities do not guarantee that all actions fit shared labor/budget constraints."], provenance={"climate_source": "NASA POWER (optional historical context)", "source_type": "user-entered scenario + illustrative decision rules", "forecast_available": False})
