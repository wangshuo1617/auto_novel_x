from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


_RANGE_PATTERNS = (
    re.compile(r"(?P<start>\d+)\s*[-~至到]\s*(?P<end>\d+)\s*章"),
    re.compile(r"第\s*(?P<start>\d+)\s*章\s*[-~至到]\s*第?\s*(?P<end>\d+)\s*章"),
)
_NUMBER_PATTERN = re.compile(r"(?P<value>\d+)\s*章")

RECENT_SUMMARY_LIMIT = 6
KNOWLEDGE_LIMIT = 30
RESOLVED_THREAD_LIMIT = 20


def story_memory_path(book_dir: str | Path) -> Path:
    return Path(book_dir) / "story_memory.json"


def empty_story_memory() -> dict[str, Any]:
    return {
        "running_summary": "",
        "recent_chapter_summaries": [],
        "active_threads": [],
        "resolved_threads": [],
        "knowledge_fragments": [],
        "last_cliffhanger": "",
        "updated_at": "",
    }


def normalize_story_memory(value: Any) -> dict[str, Any]:
    memory = empty_story_memory()
    if isinstance(value, dict):
        memory.update(value)

    for key in ("recent_chapter_summaries", "active_threads", "resolved_threads", "knowledge_fragments"):
        if not isinstance(memory.get(key), list):
            memory[key] = []

    if not isinstance(memory.get("running_summary"), str):
        memory["running_summary"] = ""
    if not isinstance(memory.get("last_cliffhanger"), str):
        memory["last_cliffhanger"] = ""
    if not isinstance(memory.get("updated_at"), str):
        memory["updated_at"] = ""

    return memory


def parse_stage_chapter_range(stage_data: dict[str, Any], fallback_start: int | None = None) -> tuple[int | None, int | None]:
    explicit = stage_data.get("chapter_range")
    if isinstance(explicit, dict):
        start = _coerce_int(explicit.get("start"))
        end = _coerce_int(explicit.get("end"))
        if start is not None and end is not None and end >= start:
            return start, end

    text_candidates = [
        str(stage_data.get("stage") or ""),
        str(stage_data.get("goal") or ""),
    ]
    for text in text_candidates:
        for pattern in _RANGE_PATTERNS:
            match = pattern.search(text)
            if match:
                start = _coerce_int(match.group("start"))
                end = _coerce_int(match.group("end"))
                if start is not None and end is not None and end >= start:
                    return start, end

    values: list[int] = []
    for text in text_candidates:
        values.extend(int(match.group("value")) for match in _NUMBER_PATTERN.finditer(text))
    if len(values) >= 2:
        start, end = values[0], values[1]
        if end >= start:
            return start, end
    if len(values) == 1 and fallback_start is not None:
        end = values[0]
        if end >= fallback_start:
            return fallback_start, end
    return None, None


def build_volume_progress(volume_plan: dict[str, Any] | None, current_chapter_num: int) -> dict[str, Any]:
    roadmap = volume_plan.get("roadmap", []) if isinstance(volume_plan, dict) else []
    normalized_stages: list[dict[str, Any]] = []
    cursor = 1
    for index, raw_stage in enumerate(roadmap, start=1):
        stage = dict(raw_stage) if isinstance(raw_stage, dict) else {"stage": str(raw_stage), "goal": ""}
        start, end = parse_stage_chapter_range(stage, fallback_start=cursor)
        if start is None:
            start = cursor
        if end is None or end < start:
            end = start + 9
        cursor = end + 1

        normalized_stages.append(
            {
                "stage_index": index,
                "stage": stage.get("stage", f"Stage {index}"),
                "goal": stage.get("goal", ""),
                "chapter_range": {"start": start, "end": end},
            }
        )

    total_planned_chapters = normalized_stages[-1]["chapter_range"]["end"] if normalized_stages else 0
    current_stage = None
    for stage in normalized_stages:
        start = stage["chapter_range"]["start"]
        end = stage["chapter_range"]["end"]
        if start <= current_chapter_num <= end:
            current_stage = stage
            break

    if current_stage is None and normalized_stages:
        current_stage = normalized_stages[-1] if current_chapter_num > total_planned_chapters else normalized_stages[0]

    completed_stages = []
    upcoming_stages = []
    if current_stage is not None:
        current_index = current_stage["stage_index"]
        completed_stages = [stage for stage in normalized_stages if stage["stage_index"] < current_index]
        upcoming_stages = [stage for stage in normalized_stages if stage["stage_index"] > current_index]

    chapters_until_stage_end = None
    stage_progress_ratio = None
    if current_stage is not None:
        start = current_stage["chapter_range"]["start"]
        end = current_stage["chapter_range"]["end"]
        chapters_until_stage_end = max(end - current_chapter_num, 0)
        stage_length = max(end - start + 1, 1)
        stage_progress_ratio = round((current_chapter_num - start + 1) / stage_length, 3)

    return {
        "current_chapter_num": current_chapter_num,
        "total_planned_chapters": total_planned_chapters,
        "current_stage": current_stage,
        "completed_stages": completed_stages,
        "upcoming_stages": upcoming_stages,
        "all_stages": normalized_stages,
        "chapters_until_stage_end": chapters_until_stage_end,
        "stage_progress_ratio": stage_progress_ratio,
    }


def merge_lore_into_story_memory(
    story_memory: dict[str, Any] | None,
    lore_data: dict[str, Any] | None,
    *,
    chapter_num: int,
    chapter_title: str,
    cliffhanger: str = "",
) -> dict[str, Any]:
    memory = normalize_story_memory(story_memory)
    lore = lore_data if isinstance(lore_data, dict) else {}

    summary_text = _clean_text(lore.get("summary_text", ""))
    running_summary = _clean_text(lore.get("rolling_story_summary", ""))
    if running_summary:
        memory["running_summary"] = running_summary
    elif summary_text:
        memory["running_summary"] = _fallback_running_summary(memory.get("running_summary", ""), summary_text)

    if summary_text:
        memory["recent_chapter_summaries"].append(
            {
                "chapter_num": chapter_num,
                "chapter_title": chapter_title,
                "summary_text": summary_text,
            }
        )
        memory["recent_chapter_summaries"] = memory["recent_chapter_summaries"][-RECENT_SUMMARY_LIMIT:]

    _merge_active_threads(memory, lore.get("plot_threads", {}))
    _merge_knowledge(memory, lore.get("knowledge_fragments", []))

    if cliffhanger:
        memory["last_cliffhanger"] = cliffhanger
    memory["updated_at"] = datetime.now().isoformat()
    return memory


def story_context_for_plot(story_memory: dict[str, Any] | None, fallback_history: list[str] | None = None) -> str:
    memory = normalize_story_memory(story_memory)
    parts: list[str] = []
    running_summary = _clean_text(memory.get("running_summary", ""))
    if running_summary:
        parts.append(f"阶段累计摘要：{running_summary}")

    recent = memory.get("recent_chapter_summaries", [])[-RECENT_SUMMARY_LIMIT:]
    if recent:
        lines = [
            f"第{item.get('chapter_num', '?')}章《{item.get('chapter_title', '')}》：{item.get('summary_text', '')}"
            for item in recent
            if isinstance(item, dict) and item.get("summary_text")
        ]
        if lines:
            parts.append("最近章节摘要：\n" + "\n".join(f"- {line}" for line in lines))
    elif fallback_history:
        lines = [entry for entry in fallback_history[-RECENT_SUMMARY_LIMIT:] if entry]
        if lines:
            parts.append("最近章节摘要：\n" + "\n".join(f"- {line}" for line in lines))

    active_threads = memory.get("active_threads", [])[:8]
    if active_threads:
        lines = [
            thread.get("description", "")
            for thread in active_threads
            if isinstance(thread, dict) and thread.get("description")
        ]
        if lines:
            parts.append("当前未完结线索：\n" + "\n".join(f"- {line}" for line in lines))

    return "\n\n".join(part for part in parts if part).strip()


def story_context_for_draft(story_memory: dict[str, Any] | None, lore_records: list[dict[str, Any]] | None = None) -> str:
    memory = normalize_story_memory(story_memory)
    parts: list[str] = []
    running_summary = _clean_text(memory.get("running_summary", ""))
    if running_summary:
        parts.append(f"累计剧情摘要：{running_summary}")

    recent = memory.get("recent_chapter_summaries", [])[-3:]
    if recent:
        lines = [
            f"第{item.get('chapter_num', '?')}章：{item.get('summary_text', '')}"
            for item in recent
            if isinstance(item, dict) and item.get("summary_text")
        ]
        if lines:
            parts.append("最近三章事实摘要：\n" + "\n".join(f"- {line}" for line in lines))

    if lore_records:
        raw_recent = []
        for record in lore_records[-3:]:
            if not isinstance(record, dict):
                continue
            output_data = record.get("output_data")
            if isinstance(output_data, str):
                try:
                    output_data = json.loads(output_data)
                except Exception:
                    output_data = {}
            elif output_data is None and record.get("summary_text"):
                output_data = record
            if isinstance(output_data, dict):
                summary = _clean_text(output_data.get("summary_text", ""))
                if summary:
                    raw_recent.append(summary)
        if raw_recent:
            parts.append("正文近景上下文：\n" + "\n".join(f"- {line}" for line in raw_recent))

    active_threads = memory.get("active_threads", [])[:5]
    if active_threads:
        lines = [
            thread.get("description", "")
            for thread in active_threads
            if isinstance(thread, dict) and thread.get("description")
        ]
        if lines:
            parts.append("当前必须承接的线索：\n" + "\n".join(f"- {line}" for line in lines))

    return "\n\n".join(part for part in parts if part).strip()


def _merge_active_threads(memory: dict[str, Any], plot_threads: Any) -> None:
    if not isinstance(plot_threads, dict):
        return

    active_by_id: dict[str, dict[str, Any]] = {}
    for thread in memory.get("active_threads", []):
        if isinstance(thread, dict):
            thread_id = str(thread.get("thread_id") or thread.get("description") or "").strip()
            if thread_id:
                active_by_id[thread_id] = thread

    for thread in plot_threads.get("opened", []):
        if not isinstance(thread, dict):
            continue
        thread_id = str(thread.get("thread_id") or thread.get("description") or "").strip()
        if not thread_id:
            continue
        active_by_id[thread_id] = {
            "thread_id": thread_id,
            "description": thread.get("description", ""),
            "involved_characters": thread.get("involved_characters", []),
        }

    closed_items = plot_threads.get("closed", [])
    resolved_threads = memory.get("resolved_threads", [])
    closed_ids = {str(item).strip() for item in closed_items if str(item).strip()}
    if closed_ids:
        next_active = []
        for thread_id, thread in active_by_id.items():
            if thread_id in closed_ids or str(thread.get("description", "")).strip() in closed_ids:
                resolved_threads.append({"thread_id": thread_id, "description": thread.get("description", "")})
                continue
            next_active.append(thread)
        memory["active_threads"] = next_active
    else:
        memory["active_threads"] = list(active_by_id.values())

    if closed_ids:
        for item in closed_ids:
            resolved_threads.append({"thread_id": item, "description": item})

    deduped_resolved: list[dict[str, Any]] = []
    seen = set()
    for item in resolved_threads:
        if not isinstance(item, dict):
            continue
        key = str(item.get("thread_id") or item.get("description") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped_resolved.append(item)
    memory["resolved_threads"] = deduped_resolved[-RESOLVED_THREAD_LIMIT:]


def _merge_knowledge(memory: dict[str, Any], knowledge_fragments: Any) -> None:
    existing = memory.get("knowledge_fragments", [])
    merged: list[dict[str, Any]] = []
    seen = set()
    for item in list(existing) + list(knowledge_fragments or []):
        if not isinstance(item, dict):
            continue
        topic = _clean_text(item.get("topic", ""))
        fact = _clean_text(item.get("fact", ""))
        if not topic and not fact:
            continue
        key = (topic, fact)
        if key in seen:
            continue
        seen.add(key)
        merged.append({"topic": topic, "fact": fact})
    memory["knowledge_fragments"] = merged[-KNOWLEDGE_LIMIT:]


def _fallback_running_summary(existing: str, latest: str) -> str:
    existing = _clean_text(existing)
    latest = _clean_text(latest)
    if not existing:
        return latest
    combined = f"{existing} {latest}".strip()
    if len(combined) <= 500:
        return combined
    return combined[-500:]


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            return None
    return None