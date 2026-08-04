from google import genai
from google.genai import types
import json,os,sys
import time
from datetime import datetime
from typing import Any

_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
from config import GEMINI_API_KEY
from utils.llm_logging import write_llm_run_log
from utils.prompt_presets import load_prompt_template

_client = None
_GEMINI_HTTP_TIMEOUT_MS = int(os.getenv("GEMINI_HTTP_TIMEOUT_MS", "300000"))
_GEMINI_MAX_RETRIES = max(1, int(os.getenv("GEMINI_MAX_RETRIES", "5")))
_GEMINI_RETRY_DELAY_SECONDS = float(os.getenv("GEMINI_RETRY_DELAY_SECONDS", "3"))


def _get_client():
  global _client
  if _client is not None:
    return _client
  if not GEMINI_API_KEY:
    raise ValueError("Missing GEMINI_API_KEY in environment.")
  _client = genai.Client(api_key=GEMINI_API_KEY)
  return _client


def _to_jsonable(value: Any) -> Any:
  if hasattr(value, "model_dump"):
    return value.model_dump(mode="json")
  return value


def _extract_candidate_text(response: Any) -> str | None:
  candidates = getattr(response, "candidates", None) or []
  for candidate in candidates:
    content = getattr(candidate, "content", None)
    parts = getattr(content, "parts", None) or []
    fragments: list[str] = []
    for part in parts:
      text = getattr(part, "text", None)
      if isinstance(text, str) and text.strip():
        fragments.append(text)
    if fragments:
      return "".join(fragments)
  return None


def _response_debug_meta(response: Any) -> dict[str, Any]:
  candidates = getattr(response, "candidates", None) or []
  return {
    "candidate_count": len(candidates),
    "finish_reasons": [str(getattr(candidate, "finish_reason", "")) for candidate in candidates],
    "prompt_feedback": _to_jsonable(getattr(response, "prompt_feedback", None)),
    "usage_metadata": _to_jsonable(getattr(response, "usage_metadata", None)),
    "response_id": getattr(response, "response_id", None),
    "model_version": getattr(response, "model_version", None),
  }


def _extract_response_payload(response: Any) -> tuple[Any, str | None]:
  parsed = _to_jsonable(getattr(response, "parsed", None))
  if parsed is not None:
    if isinstance(parsed, str):
      return json.loads(parsed), parsed
    return parsed, json.dumps(parsed, ensure_ascii=False, indent=2)

  response_text = getattr(response, "text", None)
  if isinstance(response_text, str) and response_text.strip():
    return json.loads(response_text), response_text

  candidate_text = _extract_candidate_text(response)
  if candidate_text:
    return json.loads(candidate_text), candidate_text

  debug = _response_debug_meta(response)
  raise ValueError(
    "Gemini returned no structured payload: response.parsed and response.text are both empty"
    f" (candidate_count={debug['candidate_count']}, finish_reasons={debug['finish_reasons']},"
    f" prompt_feedback={debug['prompt_feedback']})"
  )


def _is_retryable_llm_error(exc: Exception) -> bool:
  # 优先看结构化状态码（google-genai 的 APIError 带 .code / .status）
  code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
  try:
    if code is not None and int(code) in (408, 429, 500, 502, 503, 504):
      return True
  except (TypeError, ValueError):
    pass
  status = str(getattr(exc, "status", "") or "").lower()
  if status in ("unavailable", "resource_exhausted", "internal", "deadline_exceeded", "aborted"):
    return True

  message = str(exc).lower()
  retryable_markers = (
    "timeout",
    "timed out",
    "deadline exceeded",
    "connection reset",
    "connection aborted",
    "remote protocol error",
    "temporarily unavailable",
    "service unavailable",
    "currently unavailable",
    "unavailable",
    "overloaded",
    "resource_exhausted",
    "resource exhausted",
    "internal server error",
    "bad gateway",
    "gateway timeout",
    "server disconnected",
    "http 408",
    "http 429",
    "http 500",
    "http 502",
    "http 503",
    "http 504",
    "408",
    "429",
    "500",
    "502",
    "503",
    "504",
  )
  return any(marker in message for marker in retryable_markers)

def gemini_client(system_prompt: str, user_prompt: str, response_schema: dict,temperature: float = 0.7) -> str:
  model = "gemini-3.1-pro-preview"
  started_at = datetime.now().isoformat(timespec="seconds")
  started_monotonic = time.monotonic()
  config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_schema=response_schema,
        temperature=temperature,
        http_options=types.HttpOptions(timeout=_GEMINI_HTTP_TIMEOUT_MS),
    )
  last_exc = None
  for attempt in range(1, _GEMINI_MAX_RETRIES + 1):
    response_text = None
    parsed_response = None
    response_debug = None
    try:
      response = _get_client().models.generate_content(
        model=model,
        contents=user_prompt,
        config=config
      )
      response_debug = _response_debug_meta(response)
      result, response_text = _extract_response_payload(response)
      parsed_response = result
      write_llm_run_log(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_schema=response_schema,
        model=model,
        temperature=temperature,
        started_at=started_at,
        started_monotonic=started_monotonic,
        response_text=response_text,
        parsed_response=parsed_response,
        response_debug=response_debug,
      )
      return result
    except Exception as exc:
      last_exc = exc
      write_llm_run_log(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_schema=response_schema,
        model=model,
        temperature=temperature,
        started_at=started_at,
        started_monotonic=started_monotonic,
        response_text=response_text,
        parsed_response=parsed_response,
        response_debug=response_debug,
        error=exc,
      )
      if attempt >= _GEMINI_MAX_RETRIES or not _is_retryable_llm_error(exc):
        raise
      backoff = _GEMINI_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
      print(
        f"⚠ Gemini 请求失败（尝试 {attempt}/{_GEMINI_MAX_RETRIES}）：{exc}；"
        f" {backoff:.0f} 秒后重试..."
      )
      time.sleep(backoff)
  raise last_exc

def gemini_translate(
    system_prompt: str,
    user_prompt: str,
    model: str = "gemini-3.1-flash-lite",
    temperature: float = 0.3,
) -> str:
  """纯文本翻译客户端：不带 response_schema，直接返回文本，不做 json.loads。

  与 gemini_client 平行，专供章节翻译等纯文本场景使用；复用重试逻辑与 run log。
  """
  started_at = datetime.now().isoformat(timespec="seconds")
  started_monotonic = time.monotonic()
  config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=temperature,
        http_options=types.HttpOptions(timeout=_GEMINI_HTTP_TIMEOUT_MS),
    )
  last_exc = None
  for attempt in range(1, _GEMINI_MAX_RETRIES + 1):
    response_text = None
    response_debug = None
    try:
      response = _get_client().models.generate_content(
        model=model,
        contents=user_prompt,
        config=config
      )
      response_debug = _response_debug_meta(response)
      response_text = getattr(response, "text", None) or _extract_candidate_text(response)
      if not response_text or not response_text.strip():
        raise ValueError(
          "Gemini 翻译返回空文本"
          f"（candidate_count={response_debug['candidate_count']},"
          f" finish_reasons={response_debug['finish_reasons']},"
          f" prompt_feedback={response_debug['prompt_feedback']}）"
        )
      write_llm_run_log(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_schema={},
        model=model,
        temperature=temperature,
        started_at=started_at,
        started_monotonic=started_monotonic,
        response_text=response_text,
        parsed_response=response_text,
        response_debug=response_debug,
      )
      return response_text
    except Exception as exc:
      last_exc = exc
      write_llm_run_log(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_schema={},
        model=model,
        temperature=temperature,
        started_at=started_at,
        started_monotonic=started_monotonic,
        response_text=response_text,
        parsed_response=None,
        response_debug=response_debug,
        error=exc,
      )
      if attempt >= _GEMINI_MAX_RETRIES or not _is_retryable_llm_error(exc):
        raise
      backoff = _GEMINI_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
      print(
        f"⚠ Gemini 翻译请求失败（尝试 {attempt}/{_GEMINI_MAX_RETRIES}）：{exc}；"
        f" {backoff:.0f} 秒后重试..."
      )
      time.sleep(backoff)
  raise last_exc


def load_prompt_config(template_name: str,type: str, **kwargs) -> str:
  template_config = load_prompt_template(template_name)
  if "schema" not in type:
    key = f"{type}_prompt"
    if key not in template_config:
      raise ValueError(f"{template_name} 缺少 prompt 字段: {key}")
    return template_config[key].format(**kwargs)
  key = "json_schema"
  if key not in template_config:
    raise ValueError(f"{template_name} 缺少 schema 字段: {key}")
  return template_config[key]
    
if __name__ == "__main__":
  system_prompt = load_prompt_config("world_architect_prompt", "system")
  user_prompt = load_prompt_config("world_architect_prompt", "user", trend_analysis="aaaaaaaaaa")
  schema = load_prompt_config("world_architect_prompt", "json_schema")
  result = gemini_client(system_prompt, user_prompt,schema)
  print(result)