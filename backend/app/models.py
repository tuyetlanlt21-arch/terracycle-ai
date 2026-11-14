from typing import Literal
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, field_validator

Priority = Literal["yield", "water", "soil", "income", "risk"]
Strategy = Literal["current_practice", "water_saving", "soil_recovery"]
Status = Literal["PASS", "FAIL", "UNKNOWN"]

class FarmProfile(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    current_crop: str = Field(min_length=1, max_length=100)
    farm_area_ha: float = Field(gt=0, le=100000)
    soil_ph: float | None = Field(default=None, ge=3.5, le=9)
    soil_salinity_ec: float | None = Field(default=None, ge=0)
    irrigation_water_ec: float | None = Field(default=None, ge=0)
    irrigation_available: bool | None = None
    freshwater_availability: Literal["unknown", "limited", "adequate"] = "unknown"
    farmer_priority: Priority = "yield"
    planning_month: int | None = Field(default=None, ge=1, le=12)
    planting_date: date | None = None

    @field_validator("current_crop")
    @classmethod
    def current_crop_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("current_crop must not be blank")
        return value

class CropProfile(BaseModel):
    crop_id: str
    crop_name: str
    temperature_min_c: float | None = None
    temperature_max_c: float | None = None
    rainfall_min_mm: float | None = None
    rainfall_max_mm: float | None = None
    soil_ph_min: float | None = None
    soil_ph_max: float | None = None
    growth_duration_days: int | None = Field(default=None, ge=0)
    source_reference: str

class RotationScenario(BaseModel):
    farm: FarmProfile
    strategy: Strategy
    candidate_crop_ids: list[str] = Field(default_factory=list, max_length=20)

class SuitabilityAssessment(BaseModel):
    temperature: Status
    rainfall_window: Status
    water: Status
    soil: Status
    salinity: Status

class RotationRecommendation(BaseModel):
    sequence: list[str]
    crop_id: str
    crop_name: str
    strategy: Strategy
    eligibility: Status
    score: float | None
    growth_duration_days: int | None
    hard_constraints_pass: Status
    suitability: SuitabilityAssessment
    rationale: list[str]
    warnings: list[str]
    sources: list[str]

class RejectedAlternative(BaseModel):
    crop_id: str
    sequence: list[str]
    eligibility: Status
    reasons: list[str]
    sources: list[str]

class Provenance(BaseModel):
    climate_source: str
    climate_period: str | None
    climate_source_url: str | None
    soil_status: str | None
    forecast_available: bool

class ScoringMetadata(BaseModel):
    weights: dict[str, float]
    score_definition: str
    threshold_time_basis: dict[str, str]
    annual_rainfall_policy: str
    window_rainfall_policy: str

class RotationCompareResponse(BaseModel):
    recommendations: list[RotationRecommendation]
    rejected_alternatives: list[RejectedAlternative]
    missing_data_warnings: list[str]
    warnings: list[str]
    provenance: Provenance
    scoring: ScoringMetadata
