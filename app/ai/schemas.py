"""Pydantic schemas for AI output."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class AIClusterOutput(BaseModel):
    status: Literal["publish", "reject", "hold"]
    editorial_priority: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str = ""
    summary: str = ""
    body: str = ""
    why_it_matters: str = ""
    conflicts: list[Any] = Field(default_factory=list)
    sources_used: list[Any] = Field(default_factory=list)
    rejection_reason: str = ""
    sensitivity: Literal[
        "normal", "political", "security", "casualty", "market", "medical"
    ] = "normal"
    needs_human_review: bool = False

    @field_validator("headline", "summary", "body")
    @classmethod
    def strip_html_tags(cls, v: str) -> str:
        if "<" in v or ">" in v:
            raise ValueError("HTML not allowed in headline/summary/body")
        return v.strip()


class RetractionClassifyOutput(BaseModel):
    type: Literal["update", "correction", "retraction", "noise"]
    confidence: float = Field(ge=0.0, le=1.0)
    corrected_text: str = ""


class DeltaCheckOutput(BaseModel):
    has_new_value: bool
    supplement_text: str = ""
    reason: str = ""
