import json
import re
from typing import Any, Iterable


def _parse_json_text(value: str) -> Any:
    stripped = value.strip()
    if not stripped:
        return None

    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)

    candidates = [stripped]

    object_start = stripped.find("{")
    object_end = stripped.rfind("}")
    if object_start != -1 and object_end != -1 and object_end > object_start:
        candidates.append(stripped[object_start:object_end + 1])

    array_start = stripped.find("[")
    array_end = stripped.rfind("]")
    if array_start != -1 and array_end != -1 and array_end > array_start:
        candidates.append(stripped[array_start:array_end + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception:
            continue

    return None


def extract_response_payload(response: Any, preferred_keys: Iterable[str] = ()) -> Any:
    if isinstance(response, dict):
        for key in preferred_keys:
            payload = response.get(key)
            if payload not in (None, ""):
                response = payload
                break

    if isinstance(response, str):
        parsed = _parse_json_text(response)
        return parsed if parsed is not None else response

    return response


def extract_response_object(response: Any, preferred_keys: Iterable[str] = ()) -> dict:
    payload = extract_response_payload(response, preferred_keys)
    return payload if isinstance(payload, dict) else {}


def extract_response_text(response: Any, preferred_keys: Iterable[str] = ()) -> str:
    payload = extract_response_payload(response, preferred_keys)
    if isinstance(payload, str):
        return payload
    if isinstance(payload, (dict, list)):
        return json.dumps(payload, ensure_ascii=False, indent=2)
    if payload is None:
        return ""
    return str(payload)
