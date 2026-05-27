"""
阶段2–4：单章生成流水线
策划与编剧 → 质检与风控 → 数据回写。
"""

import json, re
from typing import Any, Dict, List, Tuple

from agents import ContinuityKeeper, DraftSmith, ElementDesigner, LoreArchivist, PlotEngineer
from utils.book_artifacts import chapter_artifact_path, list_chapter_files, load_json_file, lore_artifact_path, plot_arc_artifact_path, write_json_file
from utils.story_context import (
    build_volume_progress,
    merge_lore_into_story_memory,
    story_context_for_draft,
    story_context_for_plot,
    story_memory_path,
)
from utils.structured_response import extract_response_object, extract_response_text
from workflows.review_utils import is_review_passed, run_reader_review

PLOT_ARC_CHAPTER_COUNT = 10


def run_chapter_generation(loop) -> Dict[str, Any]:
    """
    阶段2–4：生成单章内容并回写。
    会更新 loop 上的 lore_records、story_history、cliffhanger、plot_arc_index 等，并落盘章节与 lore。
    """
    print("\n" + "=" * 60)
    print(f"生成第 {loop.current_chapter_num} 章")
    print("=" * 60)

    plot_story_context = story_context_for_plot(loop.story_memory, loop.story_history)
    draft_story_context = story_context_for_draft(loop.story_memory, loop.lore_records)
    recent_raw_context = _build_recent_raw_context(loop)
    story_history_for_draft = draft_story_context + ("\n\n最近章节原文摘录：\n" + recent_raw_context if recent_raw_context else "")

    print("\n[阶段2] 策划与编剧")
    print("\n[C] 情景工程师正在规划剧情...")
    chapter_outline, plot_analysis, plot_data = _ensure_plot_arc(loop, plot_story_context)
    _ensure_current_chapter_assets(loop, chapter_outline, plot_analysis, plot_story_context)
    print(f"✓ 剧情大纲已生成: {chapter_outline.get('title', '未命名')}")

    plot_data_for_draft = _plot_data_for_draft(loop, chapter_outline)
    raw_text, chapter_title = _run_draft(loop, chapter_outline, plot_analysis, plot_data_for_draft, story_history_for_draft)
    print(f"✓ 正文初稿已生成: {chapter_title}")

    print("\n[阶段3] 质检与风控")
    audit_passed, raw_text, chapter_title, plot_data = _run_audit_phase(
        loop, raw_text, chapter_title, chapter_outline, plot_analysis, plot_data_for_draft,
        story_history_for_draft, plot_story_context, plot_data,
    )
    if not audit_passed:
        raise RuntimeError("章节生成失败，已重试 3 次")

    print("\n[阶段4] 数据回写")
    _run_writeback(loop, chapter_title, raw_text, chapter_outline)

    if loop.plot_arc and loop.plot_arc_index < len(loop.plot_arc):
        loop.plot_arc_index += 1

    return {
        "chapter_num": loop.current_chapter_num,
        "title": chapter_title,
        "content": raw_text,
        "plot_data": plot_data,
    }


def _build_lore_context(loop) -> str:
    if not loop.lore_records:
        return ""
    lore_context = "相关历史设定：\n"
    for record in loop.lore_records[-5:]:
        try:
            record_data = extract_response_object(record, ("output_data",))
            summary = record_data.get("summary_text", "")
            if summary:
                lore_context += f"- {summary}\n"
        except Exception:
            continue
    return lore_context


def _build_recent_raw_context(loop, limit: int = 2, max_chars_per_chapter: int = 1600) -> str:
    chapter_files = list_chapter_files(loop.book_dir)
    if not chapter_files:
        return ""

    parts: list[str] = []
    for chapter_file in chapter_files[-limit:]:
        try:
            with open(chapter_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except Exception:
            continue
        if not content:
            continue
        excerpt = content[:max_chars_per_chapter]
        parts.append(f"[{chapter_file.name}]\n{excerpt}")
    return "\n\n".join(parts)


def _participating_characters_for_outline(db_state: dict, chapter_outline: dict) -> List[dict]:
    participating_char_data = []
    if db_state.get("protagonist"):
        participating_char_data.append(db_state["protagonist"])
    participating_char_ids = chapter_outline.get("participating_characters", [])
    for char_id in participating_char_ids:
        for char_list in [db_state.get("supporting_characters", []), db_state.get("villains", [])]:
            for char in char_list:
                if char.get("id") == char_id:
                    participating_char_data.append(char)
                    break
    return participating_char_data


def _plot_data_for_draft(loop, chapter_outline: dict) -> dict:
    db_state = loop.db.get_state()
    participating_char_data = _participating_characters_for_outline(db_state, chapter_outline)
    participating_characters_json = json.dumps(participating_char_data, ensure_ascii=False, indent=2)
    return {
        "location_id": chapter_outline.get("location_id", ""),
        "plot_points": json.dumps(chapter_outline.get("plot_points", []), ensure_ascii=False),
        "participating_characters": participating_characters_json,
        "key_items_used": json.dumps(chapter_outline.get("key_items_used", []), ensure_ascii=False),
        "chapter_num": chapter_outline.get("chapter_num", loop.current_chapter_num),
        "expected_reader_reaction": chapter_outline.get("expected_reader_reaction", ""),
        "emotional_tone": chapter_outline.get("emotional_tone", ""),
        "cliffhanger": chapter_outline.get("cliffhanger", ""),
    }


def _ensure_current_chapter_assets(loop, chapter_outline: dict, plot_analysis: str, full_story_history: str) -> None:
    db_state = loop.db.get_state()
    missing_assets = _detect_missing_outline_assets(db_state, chapter_outline)
    if not any(missing_assets.values()):
        return

    print("\n[B*] 元素设计师正在补齐当前章所需资产...")
    review_data = {}
    feedback_text = ""
    addon_raw: dict[str, Any] = {}
    normalized_assets: dict[str, Any] = {}

    for attempt in range(3):
        element_designer = ElementDesigner(loop.get_novel_setting())
        addon_result = element_designer.run(
            mode="addon",
            request_payload=_build_specific_asset_request_payload(
                loop,
                db_state,
                chapter_outline,
                plot_analysis,
                full_story_history,
                missing_assets,
            ),
            review_feedback=feedback_text,
        )
        addon_raw = extract_response_object(addon_result, ("element_data", "output_data")) or addon_result or {}
        normalized_assets = _normalize_specific_addon_assets(loop, db_state, chapter_outline, addon_raw)

        remaining_missing = _detect_missing_outline_assets(
            _merge_db_state_for_asset_check(db_state, normalized_assets),
            chapter_outline,
        )
        if any(remaining_missing.values()):
            missing_lines = []
            if remaining_missing["location_id"]:
                missing_lines.append(f"地点 ID 未补齐：{remaining_missing['location_id']}")
            if remaining_missing["participating_characters"]:
                missing_lines.append(
                    "角色 ID 未补齐：" + ", ".join(remaining_missing["participating_characters"])
                )
            if remaining_missing["key_items_used"]:
                missing_lines.append(
                    "物品 ID 未补齐：" + ", ".join(remaining_missing["key_items_used"])
                )
            feedback_text = "\n".join(
                [
                    "你没有使用我给定的缺失资产 ID，请直接复用这些 ID 生成资产。",
                    *missing_lines,
                ]
            )
            print(f"⚠ 当前章资产仍有缺失，重试 {attempt + 1}/3：{'; '.join(missing_lines)}")
            continue

        review_data = run_reader_review(
            review_stage="element_design",
            content_to_review=addon_raw,
            context_payload={
                "world_setting": loop.get_novel_setting(),
                "db_state": db_state,
                "chapter_outline": chapter_outline,
                "plot_analysis": plot_analysis,
                "story_context": full_story_history,
                "missing_assets": missing_assets,
            },
            evaluation_focus="检查补充资产是否严格匹配当前章大纲缺口、沿用给定 ID、并能直接支撑接下来的正文创作。",
        )
        if is_review_passed(review_data):
            break
        feedback_text = "\n".join(review_data.get("improvement_suggestions", []))
        print(f"⚠ 当前章补元素审核未通过（尝试 {attempt + 1}/3）：{review_data.get('review_summary', '无反馈')}")
    else:
        raise RuntimeError(f"当前章补元素失败：{review_data.get('review_summary', feedback_text or '缺失资产未补齐')}")

    addon_file = loop.book_dir / f"volume_{loop.current_volume_num:03d}_chapter_{loop.current_chapter_num:03d}_element_addon.json"
    write_json_file(addon_file, addon_raw)

    loop.db.merge_element_data(normalized_assets)
    snapshot_file = loop.book_dir / "element_data.json"
    snapshot = load_json_file(snapshot_file, {})
    write_json_file(snapshot_file, _merge_element_snapshots(snapshot, normalized_assets))
    print(f"✓ 当前章缺失资产已补齐: {addon_file.name}")


def _detect_missing_outline_assets(db_state: dict, chapter_outline: dict) -> dict[str, Any]:
    protagonist = db_state.get("protagonist", {}) or {}
    character_ids = {
        protagonist.get("id", ""),
        *(char.get("id", "") for char in db_state.get("supporting_characters", []) if isinstance(char, dict)),
        *(char.get("id", "") for char in db_state.get("villains", []) if isinstance(char, dict)),
    }
    location_ids = {
        loc.get("id", "")
        for loc in db_state.get("locations", [])
        if isinstance(loc, dict)
    }
    item_ids = {
        item.get("id", "")
        for item in db_state.get("items", [])
        if isinstance(item, dict)
    }

    location_id = str(chapter_outline.get("location_id", "")).strip()
    participating_characters = [
        char_id
        for char_id in chapter_outline.get("participating_characters", []) or []
        if isinstance(char_id, str) and char_id.strip() and char_id not in character_ids
    ]
    key_items_used = [
        item_id
        for item_id in chapter_outline.get("key_items_used", []) or []
        if isinstance(item_id, str) and item_id.strip() and item_id not in item_ids
    ]
    return {
        "location_id": location_id if location_id and location_id not in location_ids else "",
        "participating_characters": participating_characters,
        "key_items_used": key_items_used,
    }


def _build_specific_asset_request_payload(
    loop,
    db_state: dict,
    chapter_outline: dict,
    plot_analysis: str,
    full_story_history: str,
    missing_assets: dict[str, Any],
) -> dict[str, Any]:
    protagonist = db_state.get("protagonist", {}) or {}
    protagonist_status = protagonist.get("current_status", {}) or {}
    protagonist_stats = protagonist_status.get("stats", {}) or {}
    current_power_level = (
        protagonist_stats.get("cultivation_stage")
        or protagonist_stats.get("level")
        or protagonist.get("core_archetype")
        or "未知阶段"
    )
    request_payload = {
        "goal": "为当前章补齐数据库中不存在、但本章大纲已经引用的角色、地点和物品。",
        "volume_title": (loop.volume_plan or {}).get("volume_title", ""),
        "chapter_num": loop.current_chapter_num,
        "chapter_title": chapter_outline.get("title", ""),
        "plot_analysis": plot_analysis,
        "chapter_outline": chapter_outline,
        "missing_assets": missing_assets,
        "story_context": full_story_history,
        "protagonist_status": protagonist_status,
        "requirements": [
            "如果 missing_assets 给出了角色/地点/物品 ID，必须直接复用这些 ID，不要改成新的 ID。",
            "只生成当前章立刻需要的资产，不要一次性扩写大量无关角色和设定。",
            "缺失的 key_items_used 应设计为主角本章可立即使用，避免正文阶段出现无中生有。",
            "新增角色的人设、战力和立场必须与当前卷计划、当前章情绪和剧情目标兼容。",
        ],
    }
    return {
        "world_setting_summary": _build_world_setting_summary(loop.get_novel_setting()),
        "current_power_level": current_power_level,
        "existing_assets_summary": _build_existing_assets_summary(db_state),
        "task_mode": "SPECIFIC_ASSET",
        "request_payload": json.dumps(request_payload, ensure_ascii=False, indent=2),
    }


def _build_world_setting_summary(world_setting: dict[str, Any]) -> str:
    background = world_setting.get("world_background", {}) or {}
    expectation = world_setting.get("reader_expectation", {}) or {}
    golden_finger = world_setting.get("golden_finger", {}) or {}
    parts = [
        f"世界背景：{background.get('description', '')}",
        f"核心资源：{background.get('core_resource', '')}",
        f"金手指：{golden_finger.get('name', '')} - {golden_finger.get('mechanism', '')}",
        f"前期看点：{expectation.get('early_stage_highlights', '')}",
    ]
    return "\n".join(part for part in parts if part.strip())


def _build_existing_assets_summary(db_state: dict[str, Any]) -> str:
    protagonist = db_state.get("protagonist", {}) or {}
    lines = []
    if protagonist:
        lines.append(f"主角：{protagonist.get('name', '')} @ {protagonist.get('current_status', {}).get('location_id', '')}")
    if db_state.get("supporting_characters"):
        names = ", ".join(char.get("name", "") for char in db_state["supporting_characters"][:8] if char.get("name"))
        if names:
            lines.append(f"已有配角：{names}")
    if db_state.get("villains"):
        names = ", ".join(char.get("name", "") for char in db_state["villains"][:8] if char.get("name"))
        if names:
            lines.append(f"已有反派：{names}")
    if db_state.get("locations"):
        names = ", ".join(loc.get("name", "") for loc in db_state["locations"][:8] if loc.get("name"))
        if names:
            lines.append(f"已有地点：{names}")
    if db_state.get("items"):
        names = ", ".join(item.get("name", "") for item in db_state["items"][:8] if item.get("name"))
        if names:
            lines.append(f"已有物品：{names}")
    return "\n".join(lines)


def _normalize_specific_addon_assets(loop, db_state: dict, chapter_outline: dict, addon_raw: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "supporting_characters": [],
        "villains": [],
        "locations": [],
        "items": [],
    }
    if not isinstance(addon_raw, dict):
        return normalized

    chapter_location_id = str(chapter_outline.get("location_id", "")).strip() or None
    protagonist_id = str((db_state.get("protagonist", {}) or {}).get("id", "")).strip() or None
    main_villain_id = str((loop.volume_plan or {}).get("main_villain_id", "")).strip()

    new_location_ids = []
    for loc in addon_raw.get("new_locations", []) or []:
        loc_id = str(loc.get("id", "")).strip()
        if not loc_id:
            continue
        new_location_ids.append(loc_id)
        normalized["locations"].append(
            {
                "id": loc_id,
                "name": loc.get("name", ""),
                "type": loc.get("type", ""),
                "description": loc.get("description", ""),
                "key_features": [value for value in [loc.get("danger_level", "")] if value],
            }
        )

    for char in addon_raw.get("new_characters", []) or []:
        char_id = str(char.get("id", "")).strip()
        if not char_id:
            continue
        current_status = {
            "stats": char.get("stats", {}) or {},
            "state": "active",
            "location_id": _resolve_location_id(char.get("initial_location_id"), new_location_ids) or chapter_location_id,
            "inventory_ids": [],
        }
        base = {
            "id": char_id,
            "name": char.get("name", ""),
            "role": char.get("role", ""),
            "gender": char.get("gender", ""),
            "age": char.get("age", 0),
            "core_archetype": char.get("identity", "") or char.get("role", ""),
            "personality_tags": char.get("personality_tags", []) or [],
            "appearance": char.get("appearance", ""),
            "current_status": current_status,
        }
        if _is_villain_character(char, main_villain_id):
            normalized["villains"].append(
                {
                    **base,
                    "catchphrase": char.get("catchphrase", ""),
                    "type": "MiniBoss" if char_id == main_villain_id else "Fodder",
                    "hatred_source": char.get("identity", "") or char.get("role", ""),
                    "fate_prediction": char.get("fate_prediction", "待定"),
                }
            )
        else:
            normalized["supporting_characters"].append(
                {
                    **base,
                    "catchphrase": char.get("catchphrase", ""),
                    "function_in_plot": char.get("role", ""),
                    "relationship_to_protagonist": char.get("relationship_to_protagonist", "待定"),
                }
            )

    for item in addon_raw.get("new_items", []) or []:
        item_id = str(item.get("id", "")).strip()
        if not item_id:
            continue
        normalized["items"].append(
            {
                "id": item_id,
                "name": item.get("name", ""),
                "type": item.get("type", ""),
                "rarity": item.get("rarity", ""),
                "effect_description": item.get("effect", ""),
                "placement": {
                    "type": "inventory_item" if protagonist_id else "world_object",
                    "location_id": None if protagonist_id else (_resolve_location_id(item.get("location_id"), new_location_ids) or chapter_location_id),
                    "owner_id": protagonist_id,
                },
            }
        )

    return normalized


def _resolve_location_id(raw_value: Any, known_location_ids: list[str]) -> str | None:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    if text in known_location_ids:
        return text
    for loc_id in known_location_ids:
        if loc_id and loc_id in text:
            return loc_id
    return text


def _is_villain_character(char: dict[str, Any], main_villain_id: str) -> bool:
    char_id = str(char.get("id", "")).strip()
    if main_villain_id and char_id == main_villain_id:
        return True
    role_text = " ".join(
        str(char.get(key, "")) for key in ("role", "identity", "name")
    ).lower()
    return any(token in role_text for token in ("villain", "boss", "反派", "敌", "仇"))


def _merge_db_state_for_asset_check(db_state: dict, updates: dict[str, Any]) -> dict:
    merged = {
        "protagonist": db_state.get("protagonist", {}),
        "supporting_characters": list(db_state.get("supporting_characters", [])),
        "villains": list(db_state.get("villains", [])),
        "locations": list(db_state.get("locations", [])),
        "items": list(db_state.get("items", [])),
    }
    for key in ("supporting_characters", "villains", "locations", "items"):
        merged[key].extend(updates.get(key, []))
    return merged


def _merge_element_snapshots(existing: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing) if isinstance(existing, dict) else {}
    for key in ("supporting_characters", "villains", "locations", "items"):
        existing_items = merged.get(key, []) if isinstance(merged.get(key), list) else []
        update_items = updates.get(key, []) if isinstance(updates.get(key), list) else []
        by_id = {}
        for item in existing_items:
            if isinstance(item, dict) and item.get("id"):
                by_id[item["id"]] = item
        for item in update_items:
            if isinstance(item, dict) and item.get("id"):
                by_id[item["id"]] = item
        merged[key] = list(by_id.values())
    return merged


def _parse_draft_result(draft_result: dict, current_chapter_num: int) -> Tuple[str, str]:
    raw_text = draft_result.get("draft_content", "")
    chapter_title = draft_result.get("title", f"第{current_chapter_num}章")
    if not raw_text:
        try:
            draft_data_str = draft_result.get("element_data", "")
            if draft_data_str:
                draft_data = json.loads(draft_data_str)
                raw_text = draft_data.get("draft_content", "")
                chapter_title = draft_data.get("title", chapter_title)
        except Exception:
            pass
    return raw_text, chapter_title


def _coerce_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        try:
            return int(stripped)
        except ValueError:
            return default
    return default


def _extract_json_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value

    if not isinstance(value, str):
        return {}

    stripped = value.strip()
    if not stripped:
        return {}

    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)

    candidates = [stripped]
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(stripped[start:end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue

        if isinstance(parsed, dict):
            if "plot_arc" in parsed:
                return parsed
            nested = parsed.get("element_data") or parsed.get("output_data")
            if nested is not None and nested is not value:
                nested_dict = _extract_json_dict(nested)
                if nested_dict:
                    return nested_dict
            return parsed

    return {}


def _normalize_plot_arc(plot_data: dict, start_chapter_num: int) -> dict:
    plot_arc = plot_data.get("plot_arc")
    if not isinstance(plot_arc, list):
        plot_data["plot_arc"] = []
        return plot_data

    normalized_arc = []
    for index, outline in enumerate(plot_arc):
        if not isinstance(outline, dict):
            continue
        normalized_outline = dict(outline)
        normalized_outline["chapter_num"] = start_chapter_num + index
        normalized_arc.append(normalized_outline)

    plot_data["plot_arc"] = normalized_arc
    return plot_data


def _load_plot_data_from_result(plot_result: dict, start_chapter_num: int) -> dict:
    if not isinstance(plot_result, dict):
        return {}

    raw_payload = extract_response_object(plot_result, ("element_data", "output_data")) or plot_result
    plot_data = _extract_json_dict(raw_payload)
    if not plot_data:
        return {}
    return _normalize_plot_arc(plot_data, start_chapter_num)


def _plot_arc_bounds(plot_data: dict, default_start_chapter_num: int) -> tuple[int, int]:
    plot_arc = plot_data.get("plot_arc", [])
    chapter_nums = [
        entry.get("chapter_num")
        for entry in plot_arc
        if isinstance(entry, dict) and isinstance(entry.get("chapter_num"), int)
    ]
    if chapter_nums:
        return min(chapter_nums), max(chapter_nums)
    end_chapter_num = default_start_chapter_num + max(len(plot_arc) - 1, 0)
    return default_start_chapter_num, end_chapter_num


def _save_plot_arc_files(loop, plot_data: dict) -> str:
    start_chapter_num, end_chapter_num = _plot_arc_bounds(plot_data, loop.current_chapter_num)
    range_file = plot_arc_artifact_path(loop.book_dir, loop.current_volume_num, start_chapter_num, end_chapter_num)
    write_json_file(range_file, plot_data)
    write_json_file(loop.book_dir / "plot_data.json", plot_data)
    return range_file.name


def _ensure_plot_arc(loop, full_story_history: str) -> Tuple[dict, str, dict]:
    plot_data: dict = {}
    # 检查：如果 plot_arc 为空，或当前章节索引已超过已生成大纲的范围，则需要生成新的 plot_arc
    if not loop.plot_arc or loop.plot_arc_index >= len(loop.plot_arc):
        if loop.plot_arc_index >= len(loop.plot_arc):
            print(f"✓ 已用完当前 plot_arc（已使用 {len(loop.plot_arc)} 章），调用剧情工程师生成下一段 {PLOT_ARC_CHAPTER_COUNT} 章大纲...")
        else:
            print("✓ 当前没有可用的 plot_arc，调用剧情工程师生成...")
        plot_analysis = ""
        feedback_text = ""
        review_passed = False
        for attempt in range(3):
            volume_progress = build_volume_progress(loop.volume_plan or {}, loop.current_chapter_num)
            history_with_feedback = full_story_history
            if feedback_text:
                history_with_feedback = f"{history_with_feedback}\n\n上次大纲审核反馈：\n{feedback_text}".strip()
            plot_engineer = PlotEngineer(
                world_setting=loop.get_novel_setting(),
                db_state=loop.db.get_state(),
                story_history=history_with_feedback,
                volume_plan=loop.volume_plan or {},
                volume_progress=volume_progress,
                current_chapter_num=loop.current_chapter_num,
            )
            plot_result = plot_engineer.run()
            plot_data = _load_plot_data_from_result(plot_result, loop.current_chapter_num)
            plot_data["volume_progress"] = volume_progress
            loop.plot_arc = plot_data.get("plot_arc", []) or []
            loop.plot_arc_index = 0
            plot_analysis = plot_data.get("plot_analysis", "")
            if not loop.plot_arc:
                excerpt = str(plot_result)[:400]
                print(f"⚠ 情景工程师返回了空大纲，重试 {attempt + 1}/3：{excerpt}")
                continue

            review_data = run_reader_review(
                review_stage="plot_arc",
                content_to_review=plot_data,
                context_payload={
                    "world_setting": loop.get_novel_setting(),
                    "db_state": loop.db.get_state(),
                    "story_context": full_story_history,
                    "volume_plan": loop.volume_plan or {},
                    "volume_progress": volume_progress,
                },
                evaluation_focus="检查剧情大纲是否与当前卷阶段匹配，是否承接既有剧情，并为接下来的十章提供明确推进。",
            )
            if is_review_passed(review_data):
                review_passed = True
                break
            loop.plot_arc = []
            loop.plot_arc_index = 0
            feedback_text = "\n".join(review_data.get("improvement_suggestions", []))
            print(f"⚠ 大纲审核未通过，重试 {attempt + 1}/3：{review_data.get('review_summary', '无反馈')}")

        if not loop.plot_arc or not review_passed:
            raise RuntimeError("情景工程师未生成有效的剧情大纲")
        try:
            filename = _save_plot_arc_files(loop, plot_data)
            print(f"✓ 已生成并保存 {filename} 与 plot_data.json（{len(loop.plot_arc)} 条）")
        except Exception:
            print("⚠ 已生成 plot_arc，但无法保存 plot_data.json 到磁盘")
        chapter_outline = loop.plot_arc[0]
        return chapter_outline, plot_analysis, plot_data

    chapter_outline = loop.plot_arc[loop.plot_arc_index]
    plot_analysis = ""
    try:
        with open(loop.book_dir / "plot_data.json", "r", encoding="utf-8") as f:
            saved = json.load(f)
            if isinstance(saved, dict):
                plot_analysis = saved.get("plot_analysis", "")
    except Exception:
        pass
    return chapter_outline, plot_analysis, plot_data


def _run_draft(
    loop,
    chapter_outline: dict,
    plot_analysis: str,
    plot_data_for_draft: dict,
    story_history_for_draft: str,
    rewrite_feedback: str = "",
) -> Tuple[str, str]:
    print("\n[E] 正文塑造者正在创作正文...")
    draft_context = story_history_for_draft
    if rewrite_feedback:
        draft_context = f"{draft_context}\n\n本章重写要求：\n{rewrite_feedback}".strip()
    draft_smith = DraftSmith(
        world_setting=loop.get_novel_setting(),
        db_state=loop.db.get_state(),
        story_history=draft_context,
        cliffhanger=loop.cliffhanger,
        plot_analysis=plot_analysis,
        plot_data=plot_data_for_draft,
    )
    draft_result = draft_smith.run()
    return _parse_draft_result(draft_result, loop.current_chapter_num)


def _run_audit_phase(
    loop,
    raw_text: str,
    chapter_title: str,
    chapter_outline: dict,
    plot_analysis: str,
    plot_data_for_draft: dict,
    story_history_for_draft: str,
    full_story_history: str,
    plot_data: dict,
) -> Tuple[bool, str, str, dict]:
    max_retries = 3
    retry_count = 0
    audit_passed = False

    while retry_count < max_retries and not audit_passed:
        print(f"\n[I] 毒舌书评人正在审核... (尝试 {retry_count + 1}/{max_retries})")
        review_data = run_reader_review(
            review_stage="chapter_draft",
            content_to_review=raw_text,
            context_payload={
                "chapter_outline": chapter_outline,
                "plot_analysis": plot_analysis,
                "plot_data": plot_data,
                "story_context": full_story_history,
                "cliffhanger": loop.cliffhanger,
            },
            evaluation_focus="检查正文是否兑现当前章大纲、承接既有剧情、并提供足够的阅读快感与追更欲。",
        ) or {"decision": "PASS", "score": 3}

        decision = review_data.get("decision", "PASS")
        score = _coerce_int(review_data.get("score", 3), 3)

        if decision == "REWRITE" or score < 3:
            print(f"✗ 审核未通过 (评分: {score}/5)")
            print(f"  反馈: {review_data.get('review_summary', '无')}")
            if retry_count < max_retries - 1:
                rewrite_feedback = "\n".join(review_data.get("improvement_suggestions", []))
                raw_text, chapter_title = _run_draft(
                    loop,
                    chapter_outline,
                    plot_analysis,
                    plot_data_for_draft,
                    story_history_for_draft,
                    rewrite_feedback=rewrite_feedback,
                )
            retry_count += 1
            continue

        print(f"✓ 爽度审核通过 (评分: {score}/5)")
        print("\n[J] 连贯性守门员正在检查逻辑...")
        continuity_keeper = ContinuityKeeper(
            db_state=loop.db.get_state(),
            chapter_outline=json.dumps(chapter_outline, ensure_ascii=False),
            generated_text=raw_text,
        )
        continuity_result = continuity_keeper.run()
        continuity_data = extract_response_object(continuity_result, ("output_data",)) or {"audit_result": "PASS"}

        audit_result = continuity_data.get("audit_result", "PASS")
        if audit_result == "FAIL":
            print("✗ 逻辑检查未通过")
            print(f"  错误: {continuity_data.get('review_comments', '无')}")
            if retry_count < max_retries - 1:
                print("  → 重新生成正文...")
                raw_text, chapter_title = _run_draft(
                    loop,
                    chapter_outline,
                    plot_analysis,
                    plot_data_for_draft,
                    story_history_for_draft,
                    rewrite_feedback=str(continuity_data.get("review_comments", "")),
                )
            retry_count += 1
            continue

        print("✓ 逻辑检查通过")
        audit_passed = True
        database_updates = continuity_data.get("database_updates") or {}
        if database_updates:
            print("  → 更新数据库状态...")
            try:
                loop.db.update(database_updates)
            except Exception as e:
                print(f"⚠ 更新数据库时出错: {e}")

    return audit_passed, raw_text, chapter_title, plot_data
def _run_writeback(loop, chapter_title: str, raw_text: str, chapter_outline: dict) -> None:
    print("\n[G] 历史档案馆正在归档...")
    lore_archivist = LoreArchivist(
        chapter_num=loop.current_chapter_num,
        chapter_title=chapter_title,
        final_chapter_text=raw_text,
        previous_story_summary=loop.story_memory.get("running_summary", ""),
        recent_story_summaries="\n".join(loop.story_history[-3:]),
        active_threads_summary="\n".join(
            f"- {thread.get('description', '')}"
            for thread in loop.story_memory.get("active_threads", [])[:8]
            if isinstance(thread, dict) and thread.get("description")
        ),
    )
    lore_result = lore_archivist.run()
    lore_text = extract_response_text(lore_result, ("output_data",))
    lore_data = extract_response_object(lore_result, ("output_data",))
    loop.lore_records.append({"output_data": lore_data})

    lore_file = lore_artifact_path(loop.book_dir, loop.current_volume_num, loop.current_chapter_num)
    with open(lore_file, "w", encoding="utf-8") as f:
        f.write(lore_text)
    print(f"✓ 历史记录已保存: {lore_file}")

    summary = lore_data.get("summary_text", "")
    if summary:
        loop.story_history.append(summary)

    plot_threads = lore_data.get("plot_threads", {})
    opened_threads = plot_threads.get("opened", [])
    if opened_threads:
        loop.cliffhanger = opened_threads[-1].get("description", "")
    else:
        loop.cliffhanger = chapter_outline.get("cliffhanger", "")

    loop.story_memory = merge_lore_into_story_memory(
        loop.story_memory,
        lore_data,
        chapter_num=loop.current_chapter_num,
        chapter_title=chapter_title,
        cliffhanger=loop.cliffhanger,
    )
    write_json_file(story_memory_path(loop.book_dir), loop.story_memory)

    chapter_file = chapter_artifact_path(loop.book_dir, loop.current_volume_num, loop.current_chapter_num)
    with open(chapter_file, "w", encoding="utf-8") as f:
        f.write(f"# {chapter_title}\n\n")
        f.write(raw_text)
    print(f"✓ 章节已保存: {chapter_file}")
