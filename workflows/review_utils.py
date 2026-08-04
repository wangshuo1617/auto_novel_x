from __future__ import annotations

import json
from typing import Any

from agents import SimulatedReader


def run_reader_review(
    *,
    review_stage: str,
    content_to_review: Any,
    genre: str = "网文",
    context_payload: dict[str, Any] | None = None,
    evaluation_focus: str = "",
) -> dict[str, Any]:
    review_text = _to_review_text(content_to_review)
    reader = SimulatedReader(
        genre=genre,
        content_to_review=review_text,
        review_stage=review_stage,
        context_payload=context_payload or {},
        evaluation_focus=evaluation_focus,
    )
    review_result = reader.run()
    if not isinstance(review_result, dict):
        raise ValueError("SimulatedReader 必须返回 JSON 对象")
    return review_result


def is_review_passed(review_data: dict[str, Any], min_score: int = 3) -> bool:
    if not isinstance(review_data, dict):
        return False
    decision = str(review_data.get("decision", "PASS")).upper()
    score = review_data.get("score", min_score)
    try:
        numeric_score = int(score)
    except Exception:
        numeric_score = min_score
    return decision != "REWRITE" and numeric_score >= min_score


def _to_review_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)