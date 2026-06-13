"""OpenAI client with circuit breaker and json_schema fallback."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from openai import OpenAI
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.parser import parse_cluster_output
from app.ai.prompts import (
    CLUSTER_ANALYSIS_SYSTEM,
    CLUSTER_ANALYSIS_USER,
    DELTA_CHECK_USER,
    RETRACTION_CLASSIFY_USER,
    SIMPLE_JSON_RETRY,
)
from app.ai.schemas import AIClusterOutput, DeltaCheckOutput, RetractionClassifyOutput
from app.config import get_settings
from app.db.models.ai_result import AIResult


CLUSTER_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["publish", "reject", "hold"]},
        "editorial_priority": {"type": "integer", "minimum": 1, "maximum": 5},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "headline": {"type": "string"},
        "summary": {"type": "string"},
        "why_it_matters": {"type": "string"},
        "conflicts": {"type": "array"},
        "sources_used": {"type": "array"},
        "rejection_reason": {"type": "string"},
        "sensitivity": {
            "type": "string",
            "enum": ["normal", "political", "security", "casualty", "market", "medical"],
        },
        "needs_human_review": {"type": "boolean"},
    },
    "required": [
        "status", "editorial_priority", "confidence", "headline", "summary",
        "why_it_matters", "conflicts", "sources_used", "rejection_reason",
        "sensitivity", "needs_human_review",
    ],
    "additionalProperties": False,
}


def _monthly_spend(session: Session) -> float:
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = session.scalar(
        select(func.coalesce(func.sum(AIResult.cost_estimate_usd), 0.0)).where(
            AIResult.created_at >= month_start
        )
    )
    return float(total or 0.0)


def circuit_breaker_open(session: Session) -> bool:
    settings = get_settings()
    return _monthly_spend(session) >= settings.OPENAI_MONTHLY_BUDGET_USD


def _estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    # gpt-4o-mini approximate pricing
    return (prompt_tokens * 0.15 + completion_tokens * 0.60) / 1_000_000


class AIClient:
    def __init__(self, session: Session | None = None) -> None:
        settings = get_settings()
        self._settings = settings
        self._session = session
        self._client = (
            OpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=settings.OPENAI_TIMEOUT_SECONDS,
            )
            if settings.OPENAI_API_KEY
            else None
        )

    def _chat(self, system: str, user: str, *, use_schema: bool = True) -> tuple[str, int, int]:
        if not self._client:
            raise RuntimeError("OPENAI_API_KEY not configured")

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        kwargs: dict = {
            "model": self._settings.OPENAI_MODEL,
            "messages": messages,
            "max_tokens": self._settings.OPENAI_MAX_TOKENS,
        }
        if use_schema:
            try:
                kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "cluster_output",
                        "schema": CLUSTER_JSON_SCHEMA,
                        "strict": True,
                    },
                }
            except Exception:
                kwargs["response_format"] = {"type": "json_object"}
        else:
            kwargs["response_format"] = {"type": "json_object"}

        last_error = None
        for attempt in range(3):
            try:
                resp = self._client.chat.completions.create(**kwargs)
                content = resp.choices[0].message.content or ""
                usage = resp.usage
                return (
                    content,
                    usage.prompt_tokens if usage else 0,
                    usage.completion_tokens if usage else 0,
                )
            except Exception as exc:
                last_error = exc
                if "429" in str(exc) or "rate" in str(exc).lower():
                    time.sleep(2 ** attempt)
                    continue
                if use_schema and attempt == 0:
                    kwargs["response_format"] = {"type": "json_object"}
                    continue
                raise
        raise last_error  # type: ignore[misc]

    def analyze_cluster(
        self,
        messages_block: str,
        independent_source_count: int,
        cluster_score: float,
    ) -> tuple[AIClusterOutput, int, int, float]:
        if self._session and circuit_breaker_open(self._session):
            raise RuntimeError("AI circuit breaker open — monthly budget exceeded")

        user = CLUSTER_ANALYSIS_USER.format(
            messages_block=messages_block,
            independent_source_count=independent_source_count,
            cluster_score=cluster_score,
        )
        total_prompt = 0
        total_completion = 0
        last_text = ""

        for attempt in range(self._settings.AI_JSON_MAX_RETRIES + 1):
            prompt = user if attempt == 0 else SIMPLE_JSON_RETRY
            text, pt, ct = self._chat(CLUSTER_ANALYSIS_SYSTEM, prompt, use_schema=attempt == 0)
            total_prompt += pt
            total_completion += ct
            last_text = text
            try:
                parsed = parse_cluster_output(text)
                cost = _estimate_cost(total_prompt, total_completion)
                return parsed, total_prompt, total_completion, cost
            except Exception:
                continue

        raise ValueError(f"ai_parse_failed: {last_text[:200]}")

    def classify_retraction(self, published_text: str, new_text: str) -> RetractionClassifyOutput:
        user = RETRACTION_CLASSIFY_USER.format(
            published_text=published_text, new_text=new_text
        )
        text, _, _ = self._chat("You classify news updates.", user, use_schema=False)
        from app.ai.parser import parse_with_schema

        return parse_with_schema(text, RetractionClassifyOutput)

    def delta_check(self, published_text: str, new_text: str) -> DeltaCheckOutput:
        user = DELTA_CHECK_USER.format(published_text=published_text, new_text=new_text)
        text, _, _ = self._chat("You check if new info adds value.", user, use_schema=False)
        from app.ai.parser import parse_with_schema

        return parse_with_schema(text, DeltaCheckOutput)
