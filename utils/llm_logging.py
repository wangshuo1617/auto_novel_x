from __future__ import annotations

import contextlib
import contextvars
import inspect
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator


_LLM_LOG_CONTEXT: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar("llm_log_context", default=None)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextlib.contextmanager
def use_llm_log_context(book_dir: str | Path, operation: str = "") -> Iterator[None]:
    context = {
        "book_dir": str(Path(book_dir)),
        "operation": operation,
    }
    token = _LLM_LOG_CONTEXT.set(context)
    try:
        yield
    finally:
        _LLM_LOG_CONTEXT.reset(token)


def write_llm_run_log(
    *,
    system_prompt: str,
    user_prompt: str,
    response_schema: dict[str, Any],
    model: str,
    temperature: float,
    started_at: str,
    started_monotonic: float,
    response_text: str | None = None,
    parsed_response: Any = None,
    error: BaseException | None = None,
) -> None:
    context = _LLM_LOG_CONTEXT.get()
    if not context:
        return

    book_dir = Path(context["book_dir"])
    log_dir = book_dir / "llm_runs"
    log_dir.mkdir(parents=True, exist_ok=True)
    ended_at = _now()
    duration_ms = int((time.monotonic() - started_monotonic) * 1000)
    caller = _caller_info()
    payload = {
        "status": "failed" if error else "completed",
        "operation": context.get("operation", ""),
        "model": model,
        "temperature": temperature,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_ms": duration_ms,
        "caller": caller,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "response_schema": response_schema,
        "response_text": response_text,
        "parsed_response": parsed_response,
        "error": {"type": type(error).__name__, "message": str(error)} if error else None,
    }
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{caller['function']}.json"
    with open(log_dir / filename, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)


def list_llm_run_logs(book_dir: str | Path, limit: int = 20) -> list[dict[str, Any]]:
    log_dir = Path(book_dir) / "llm_runs"
    if not log_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(log_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            data = {"status": "unreadable", "error": str(exc)}
        rows.append(
            {
                "path": str(path.relative_to(Path(book_dir))),
                "status": data.get("status", ""),
                "operation": data.get("operation", ""),
                "model": data.get("model", ""),
                "duration_ms": data.get("duration_ms", 0),
                "caller": data.get("caller", {}),
                "started_at": data.get("started_at", ""),
                "error": data.get("error"),
                "detail": data,
            }
        )
    return rows


def _caller_info() -> dict[str, str]:
    for frame in inspect.stack()[2:]:
        filename = frame.filename.replace("\\", "/")
        if filename.endswith("/utils/llm_client.py") or filename.endswith("/utils/llm_logging.py"):
            continue
        return {
            "file": filename,
            "function": frame.function,
        }
    return {"file": "", "function": "unknown"}
