from pydantic import BaseModel, Field, field_validator
from typing import List, Literal


DecisionType = Literal["Approved", "Partially Approved", "Rejected", "Manual Review"]


class ClaimDecision(BaseModel):
    claim_id: str
    decision: DecisionType
    approved_amount: float = Field(ge=0)
    deducted_amount: float = Field(ge=0)
    missing_documents: List[str] = Field(default_factory=list)
    policy_reference: str
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    tools_used: List[str] = Field(default_factory=list)

    @field_validator("explanation")
    @classmethod
    def explanation_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("explanation must not be empty")
        return v.strip()

    class Config:
        extra = "forbid"
