from pydantic import BaseModel, field_validator

class ColumnMapping(BaseModel):
    source: str
    target: str
    confidence: float

    @field_validator("target")
    @classmethod
    def target_must_be_known(cls, v: str) -> str:
        allowed = {
            "date", "campaign_id", "impressions",
            "clicks", "spend", "conversions", "ctr", "cpc"
        }
        if v not in allowed:
            raise ValueError(f"Unknown target field: {v}")
        return v

class MappingResult(BaseModel):
    mappings: list[ColumnMapping]
    unmapped: list[str] = []
    error_message: str | None = None
