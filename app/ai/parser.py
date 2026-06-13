"""JSON parsing with retry."""

import json
import re
from typing import Type, TypeVar

from pydantic import BaseModel

from app.ai.prompts import SIMPLE_JSON_RETRY
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


def parse_with_schema(text: str, schema: Type[T]) -> T:
    blob = extract_json_blob(text)
    data = json.loads(blob)
    return schema.model_validate(data)


def parse_cluster_output(text: str) -> AIClusterOutput:
    return parse_with_schema(text, AIClusterOutput)
