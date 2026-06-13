"""JSON parsing with retry."""

import json
import re
from typing import Any, Type, TypeVar

from pydantic import BaseModel

from app.ai.schemas import AIClusterOutput

T = TypeVar("T", bound=BaseModel)


def extract_json_blob(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text


def normalize_cluster_data(data: dict[str, Any]) -> dict[str, Any]:
    """Map common GPT field variants to our schema."""
    normalized = dict(data)

    if not normalized.get("headline"):
        normalized["headline"] = (
            normalized.pop("title", None)
            or normalized.pop("headline_fa", None)
            or ""
        )
    if not normalized.get("summary"):
        normalized["summary"] = (
            normalized.pop("content", None)
            or normalized.pop("body", None)
            or normalized.pop("summary_fa", None)
            or ""
        )
    if not normalized.get("why_it_matters"):
        normalized["why_it_matters"] = normalized.pop("why_it_matters", "") or ""

    if "claims" in normalized and not normalized.get("conflicts"):
        claims = normalized.pop("claims")
        if isinstance(claims, list):
            normalized["conflicts"] = [
                c if isinstance(c, str) else str(c.get("claim", c))
                for c in claims
                if c
            ]

    if "sources" in normalized and not normalized.get("sources_used"):
        normalized["sources_used"] = normalized.pop("sources")

    if "status" not in normalized:
        normalized["status"] = "publish" if normalized.get("headline") else "reject"
    if "editorial_priority" not in normalized:
        normalized["editorial_priority"] = 3
    if "confidence" not in normalized:
        normalized["confidence"] = 0.7
    if "sensitivity" not in normalized:
        normalized["sensitivity"] = "normal"
    if "needs_human_review" not in normalized:
        normalized["needs_human_review"] = False
    if "rejection_reason" not in normalized:
        normalized["rejection_reason"] = ""
    if "conflicts" not in normalized:
        normalized["conflicts"] = []
    if "sources_used" not in normalized:
        normalized["sources_used"] = []

    return normalized


def parse_with_schema(text: str, schema: Type[T]) -> T:
    blob = extract_json_blob(text)
    data = json.loads(blob)
    if schema is AIClusterOutput:
        data = normalize_cluster_data(data)
    return schema.model_validate(data)


def parse_cluster_output(text: str) -> AIClusterOutput:
    try:
        return parse_with_schema(text, AIClusterOutput)
    except Exception:
        fallback = _extract_title_content_fallback(text)
        if fallback:
            return AIClusterOutput.model_validate(normalize_cluster_data(fallback))
        raise


def _extract_title_content_fallback(text: str) -> dict[str, Any] | None:
    """Recover from GPT responses that use title/content instead of schema."""
    data: dict[str, Any] = {}
    for src_key, dst_key in (("title", "headline"), ("content", "summary"), ("headline", "headline"), ("summary", "summary")):
        match = re.search(rf'"{re.escape(src_key)}"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if match and dst_key not in data:
            data[dst_key] = match.group(1)
    return data if data.get("headline") or data.get("summary") else None
