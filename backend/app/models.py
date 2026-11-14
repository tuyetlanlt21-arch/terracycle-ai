from typing import Literal
from pydantic import BaseModel, Field, model_validator

Stage = Literal["concentrating", "crystallizing", "ready"]
Action = Literal["harvest_early", "protect", "continue", "postpone"]

class SaltField(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    area_m2: float = Field(gt=0, le=1_000_000)
    stage: Stage
    days_to_harvest: int = Field(ge=0, le=120)
    expected_value_vnd: float = Field(ge=0)
    protection_cost_vnd: float = Field(ge=0)
    protection_available: bool = False

class ScenarioRequest(BaseModel):
    fields: list[SaltField] = Field(min_length=1, max_length=20)
    rain_mm: float = Field(ge=0, le=500)
    hours_until_rain: float = Field(ge=0, le=240)
    available_workers: int = Field(ge=0, le=100)
    available_budget_vnd: float = Field(ge=0)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [f.id for f in self.fields]
        if len(ids) != len(set(ids)):
            raise ValueError("field ids must be unique")
        return self

class ActionOption(BaseModel):
    action: Action
    field_id: str
    priority: int
    rationale: list[str]
    estimated_cost_vnd: float
    assumption: str

class CompareResponse(BaseModel):
    scenario: dict[str, float]
    actions: list[ActionOption]
    warnings: list[str]
    provenance: dict[str, str | bool]
