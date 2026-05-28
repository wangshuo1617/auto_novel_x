"""
阶段2–4：单章生成流水线
策划与编剧 → 质检与风控 → 数据回写。
"""

import json
from typing import Any, Dict, List, Tuple

from agents import ContinuityKeeper, DraftSmith, ElementDesigner, LoreArchivist, PlotEngineer
from utils.book_artifacts import (
    chapter_artifact_path,
    list_chapter_files,
    list_plot_files,
    load_json_file,
    lore_artifact_path,
    parse_plot_range_identity,
    plot_arc_artifact_path,
    write_json_file,
)
from utils.generation_state import GenerationStateTracker
from utils.story_context import (
    build_volume_progress,
    merge_lore_into_story_memory,
    story_context_for_draft,
    story_context_for_plot,
    story_memory_path,
)
from workflows.review_utils import is_review_passed, run_reader_review

PLOT_ARC_CHAPTER_COUNT = 10


def run_chapter_generation(loop) -> Dict[str, Any]:
    """
    阶段2–4：生成单章内容并回写。
    会更新 loop 上的 lore_records、story_memory、cliffhanger、plot_arc_index 等，并落盘章节与 lore。
    """
    print("\n" + "=" * 60)
    print(f"生成第 {loop.current_volume_num} 卷第 {loop.current_chapter_num} 章（全书第 {loop.current_global_chapter_num} 章）")
    print("=" * 60)
    tracker = GenerationStateTracker(
        loop.book_dir,
        loop.current_volume_num,
        loop.current_chapter_num,
        loop.current_global_chapter_num,
    )

    try:
        plot_story_context = story_context_for_plot(loop.story_memory)
        draft_story_context = story_context_for_draft(loop.story_memory, loop.lore_records)
        previous_chapter_ending = _build_previous_chapter_ending(loop)
        tracker.phase("context_prepared")

        print("\n[阶段2] 策划与编剧")
        print("\n[C] 情景工程师正在规划剧情...")
        tracker.phase("plot_planning", "running")
        chapter_outline, plot_analysis, plot_data = _ensure_plot_arc(loop, plot_story_context)
        tracker.phase("plot_planning", "completed", {"title": chapter_outline.get("title", "")})
        tracker.phase("asset_check", "running")
        _ensure_current_chapter_assets(loop, chapter_outline, plot_analysis, plot_story_context)
        tracker.phase("asset_check", "completed")
        print(f"✓ 剧情大纲已生成: {chapter_outline.get('title', '未命名')}")

        plot_data_for_draft = _plot_data_for_draft(loop, chapter_outline)
        tracker.phase("draft", "running")
        raw_text, chapter_title = _run_draft(
            loop,
            chapter_outline,
            plot_analysis,
            plot_data_for_draft,
            draft_story_context,
            previous_chapter_ending,
        )
        tracker.phase("draft", "completed", {"title": chapter_title, "characters": len(raw_text)})
        print(f"✓ 正文初稿已生成: {chapter_title}")

        print("\n[阶段3] 质检与风控")
        tracker.phase("audit", "running")
        audit_passed, raw_text, chapter_title, plot_data, plot_data_for_draft = _run_audit_phase(
            loop, raw_text, chapter_title, chapter_outline, plot_analysis, plot_data_for_draft,
            draft_story_context, plot_story_context, plot_data, previous_chapter_ending, tracker,
        )
        if not audit_passed:
            raise RuntimeError("章节生成失败，已重试 3 次")
        tracker.phase("audit", "completed")

        print("\n[阶段4] 数据回写")
        tracker.phase("writeback", "running")
        _run_writeback(loop, chapter_title, raw_text, chapter_outline)
        tracker.phase("writeback", "completed")

        if loop.plot_arc and loop.plot_arc_index < len(loop.plot_arc):
            loop.plot_arc_index += 1

        result = {
            "chapter_num": loop.current_chapter_num,
            "global_chapter_num": loop.current_global_chapter_num,
            "title": chapter_title,
            "content": raw_text,
            "plot_data": plot_data,
        }
        tracker.set_artifacts(
            {
                "chapter": chapter_artifact_path(loop.book_dir, loop.current_volume_num, loop.current_chapter_num).name,
                "lore": lore_artifact_path(loop.book_dir, loop.current_volume_num, loop.current_chapter_num).name,
                "story_memory": story_memory_path(loop.book_dir).name,
            }
        )
        tracker.complete({"title": chapter_title})
        return result
    except Exception as exc:
        tracker.fail(exc)
        raise


def _build_lore_context(loop) -> str:
    if not loop.lore_records:
        return ""
    lore_context = "相关历史设定：\n"
    for record in loop.lore_records[-5:]:
        try:
            record_data = record if isinstance(record, dict) else {}
            summary = record_data.get("summary_text", "")
            if summary:
                lore_context += f"- {summary}\n"
        except Exception:
            continue
    return lore_context


def _build_previous_chapter_ending(loop, max_chars: int = 600) -> str:
    chapter_files = list_chapter_files(loop.book_dir)
    if not chapter_files:
        return ""

    last_chapter = chapter_files[-1]
    try:
        with open(last_chapter, "r", encoding="utf-8") as f:
            content = f.read().strip()
    except Exception:
        return ""
    if not content:
        return ""
    return content[-max_chars:]


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
    return {
        "location_id": chapter_outline.get("location_id", ""),
        "plot_points": chapter_outline.get("plot_points", []) or [],
        "participating_characters": participating_char_data,
        "key_items_used": chapter_outline.get("key_items_used", []) or [],
        "chapter_num": chapter_outline.get("chapter_num", loop.current_chapter_num),
        "expected_reader_reaction": chapter_outline.get("expected_reader_reaction", ""),
        "emotional_tone": chapter_outline.get("emotional_tone", ""),
        "chapter_cliffhanger": chapter_outline.get("cliffhanger", ""),
    }


def _ensure_current_chapter_assets(loop, chapter_outline: dict, plot_analysis: str, full_story_history: str) -> None:
    db_state = loop.db.get_state()
    missing_assets = _detect_missing_outline_assets(db_state, chapter_outline)
    if not any(missing_assets.values()):
        return

    _supplement_specific_assets(
        loop,
        chapter_outline,
        plot_analysis,
        full_story_history,
        missing_assets,
        supplement_source="outline",
    )


def _supplement_specific_assets(
    loop,
    chapter_outline: dict,
    plot_analysis: str,
    full_story_history: str,
    missing_assets: dict[str, Any],
    *,
    asset_requirement_hints: dict[str, Any] | None = None,
    supplement_source: str,
) -> None:
    db_state = loop.db.get_state()
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
                asset_requirement_hints=asset_requirement_hints or {},
            ),
            review_feedback=feedback_text,
        )
        if not isinstance(addon_result, dict):
            raise ValueError("ElementDesigner addon 必须返回 JSON 对象")
        addon_raw = addon_result
        normalized_assets = _normalize_specific_addon_assets(loop, db_state, chapter_outline, addon_raw)

        expected_missing = _expected_missing_assets_after_addon(missing_assets)
        merged_db_state = _merge_db_state_for_asset_check(db_state, normalized_assets)
        unresolved = _remaining_expected_assets_in_db(merged_db_state, expected_missing)
        if _has_missing_assets(unresolved):
            missing_lines = []
            if unresolved["location_id"]:
                missing_lines.append(f"地点 ID 未补齐：{unresolved['location_id']}")
            if unresolved["participating_characters"]:
                missing_lines.append(
                    "角色 ID 未补齐：" + ", ".join(unresolved["participating_characters"])
                )
            if unresolved["key_items_used"]:
                missing_lines.append(
                    "物品 ID 未补齐：" + ", ".join(unresolved["key_items_used"])
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
                "asset_requirement_hints": asset_requirement_hints or {},
                "supplement_source": supplement_source,
            },
            evaluation_focus="检查补充资产是否严格匹配当前章大纲缺口、沿用给定 ID、并能直接支撑接下来的正文创作。",
        )
        if is_review_passed(review_data):
            break
        feedback_text = _build_review_feedback_text(review_data)
        print(f"⚠ 当前章补元素审核未通过（尝试 {attempt + 1}/3）：{review_data.get('review_summary', '无反馈')}")
    else:
        raise RuntimeError(f"当前章补元素失败：{review_data.get('review_summary', feedback_text or '缺失资产未补齐')}")

    addon_file = loop.book_dir / f"volume_{loop.current_volume_num:03d}_chapter_{loop.current_chapter_num:03d}_element_addon_{supplement_source}.json"
    write_json_file(addon_file, addon_raw)

    loop.db.merge_element_data(normalized_assets)
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
    asset_requirement_hints: dict[str, Any] | None = None,
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
        "asset_requirement_hints": asset_requirement_hints or {},
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


def _expected_missing_assets_after_addon(missing_assets: dict[str, Any]) -> dict[str, Any]:
    return {
        "location_id": str(missing_assets.get("location_id", "")).strip(),
        "participating_characters": _normalize_missing_asset_id_list(missing_assets.get("participating_characters")),
        "key_items_used": _normalize_missing_asset_id_list(missing_assets.get("key_items_used")),
    }


def _normalize_missing_asset_id_list(raw_items: Any) -> list[str]:
    normalized: list[str] = []
    for item in raw_items or []:
        if isinstance(item, dict):
            candidate = str(item.get("id", "")).strip()
        else:
            candidate = str(item).strip()
        if candidate:
            normalized.append(candidate)
    return normalized


def _remaining_expected_assets_in_db(db_state: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
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
    return {
        "location_id": expected.get("location_id", "") if expected.get("location_id") and expected.get("location_id") not in location_ids else "",
        "participating_characters": [
            item for item in expected.get("participating_characters", [])
            if item not in character_ids
        ],
        "key_items_used": [
            item for item in expected.get("key_items_used", [])
            if item not in item_ids
        ],
    }


def _has_missing_assets(missing_assets: dict[str, Any]) -> bool:
    return bool(
        str(missing_assets.get("location_id", "")).strip()
        or (missing_assets.get("participating_characters") or [])
        or (missing_assets.get("key_items_used") or [])
    )


def _extract_continuity_missing_assets(continuity_data: dict[str, Any]) -> dict[str, Any]:
    if str(continuity_data.get("failure_type", "")).upper() != "ASSET_MISSING":
        return {"location_id": "", "participating_characters": [], "key_items_used": []}
    hints = continuity_data.get("missing_asset_requirements") or {}
    location_data = hints.get("location") or {}
    return {
        "location_id": str(location_data.get("id", "")).strip(),
        "participating_characters": _normalize_missing_asset_id_list(hints.get("characters")),
        "key_items_used": _normalize_missing_asset_id_list(hints.get("items")),
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


def _parse_draft_result(draft_result: dict, current_chapter_num: int) -> Tuple[str, str]:
    if not isinstance(draft_result, dict):
        raise ValueError("DraftSmith 必须返回 JSON 对象")
    raw_text = draft_result.get("draft_content", "")
    chapter_title = draft_result.get("title", f"第{current_chapter_num}章")
    if not raw_text:
        raise ValueError("DraftSmith 返回缺少 draft_content")
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
        raise ValueError("PlotEngineer 必须返回 JSON 对象")
    return _normalize_plot_arc(plot_result, start_chapter_num)


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
    plot_data["volume_num"] = loop.current_volume_num
    start_chapter_num, end_chapter_num = _plot_arc_bounds(plot_data, loop.current_chapter_num)
    range_file = plot_arc_artifact_path(loop.book_dir, loop.current_volume_num, start_chapter_num, end_chapter_num)
    write_json_file(range_file, plot_data)
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
            plot_engineer = PlotEngineer(
                world_setting=loop.get_novel_setting(),
                db_state=loop.db.get_state(),
                story_history=full_story_history,
                volume_plan=loop.volume_plan or {},
                volume_progress=volume_progress,
                current_chapter_num=loop.current_chapter_num,
                review_feedback=feedback_text,
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
            feedback_text = _build_review_feedback_text(review_data)
            print(f"⚠ 大纲审核未通过，重试 {attempt + 1}/3：{review_data.get('review_summary', '无反馈')}")

        if not loop.plot_arc or not review_passed:
            raise RuntimeError("情景工程师未生成有效的剧情大纲")
        try:
            filename = _save_plot_arc_files(loop, plot_data)
            print(f"✓ 已生成并保存 {filename}（{len(loop.plot_arc)} 条）")
        except Exception:
            print("⚠ 已生成 plot_arc，但无法保存剧情大纲到磁盘")
        chapter_outline = loop.plot_arc[0]
        return chapter_outline, plot_analysis, plot_data

    chapter_outline = loop.plot_arc[loop.plot_arc_index]
    plot_data = _load_current_plot_data(loop)
    plot_analysis = plot_data.get("plot_analysis", "") if plot_data else ""
    if not plot_data:
        plot_data = {
            "plot_arc": list(loop.plot_arc),
            "plot_analysis": plot_analysis,
        }
    return chapter_outline, plot_analysis, plot_data


def _load_current_plot_data(loop) -> dict:
    for plot_file in list_plot_files(loop.book_dir):
        identity = parse_plot_range_identity(plot_file)
        if not identity:
            continue
        file_volume, start_chapter, end_chapter = identity
        if file_volume != loop.current_volume_num:
            continue
        if not start_chapter <= loop.current_chapter_num <= end_chapter:
            continue
        plot_data = load_json_file(plot_file, {})
        return plot_data if isinstance(plot_data, dict) else {}
    return {}


def _run_draft(
    loop,
    chapter_outline: dict,
    plot_analysis: str,
    plot_data_for_draft: dict,
    story_history_for_draft: str,
    previous_chapter_ending: str,
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
        previous_chapter_ending=previous_chapter_ending,
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
    previous_chapter_ending: str,
    tracker: GenerationStateTracker | None = None,
) -> Tuple[bool, str, str, dict, dict]:
    max_retries = 3
    retry_count = 0
    audit_passed = False

    while retry_count < max_retries and not audit_passed:
        print(f"\n[I] 毒舌书评人正在审核... (尝试 {retry_count + 1}/{max_retries})")
        if tracker:
            tracker.phase("reader_review", "running", {"attempt": retry_count + 1})
        review_data = run_reader_review(
            review_stage="chapter_draft",
            content_to_review=raw_text,
            context_payload={
                "chapter_outline": chapter_outline,
                "plot_analysis": plot_analysis,
                "plot_data": plot_data,
                "story_context": full_story_history,
                "previous_chapter_ending": previous_chapter_ending,
                "chapter_cliffhanger": chapter_outline.get("cliffhanger", ""),
            },
            evaluation_focus="检查正文是否兑现当前章大纲、承接既有剧情、并提供足够的阅读快感与追更欲。",
        ) or {"decision": "PASS", "score": 3}

        decision = review_data.get("decision", "PASS")
        score = _coerce_int(review_data.get("score", 3), 3)
        if tracker:
            tracker.phase("reader_review", "completed", {"attempt": retry_count + 1, "decision": decision, "score": score})

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
                    previous_chapter_ending,
                    rewrite_feedback=rewrite_feedback,
                )
            retry_count += 1
            continue

        print(f"✓ 爽度审核通过 (评分: {score}/5)")
        print("\n[J] 连贯性守门员正在检查逻辑...")
        if tracker:
            tracker.phase("continuity_check", "running", {"attempt": retry_count + 1})
        continuity_keeper = ContinuityKeeper(
            db_state=loop.db.get_state(),
            chapter_outline=json.dumps(chapter_outline, ensure_ascii=False),
            generated_text=raw_text,
        )
        continuity_result = continuity_keeper.run()
        if not isinstance(continuity_result, dict):
            raise ValueError("ContinuityKeeper 必须返回 JSON 对象")
        continuity_data = continuity_result

        audit_result = continuity_data.get("audit_result", "PASS")
        if tracker:
            tracker.phase("continuity_check", "completed", {"attempt": retry_count + 1, "audit_result": audit_result})
        if audit_result == "FAIL":
            print("✗ 逻辑检查未通过")
            print(f"  错误: {continuity_data.get('review_comments', '无')}")
            if retry_count < max_retries - 1:
                missing_assets = _extract_continuity_missing_assets(continuity_data)
                if _has_missing_assets(missing_assets):
                    print("  → 检测到缺资产，先补元素再重写正文...")
                    _supplement_specific_assets(
                        loop,
                        chapter_outline,
                        plot_analysis,
                        full_story_history,
                        missing_assets,
                        asset_requirement_hints=continuity_data.get("missing_asset_requirements") or {},
                        supplement_source="continuity",
                    )
                    plot_data_for_draft = _plot_data_for_draft(loop, chapter_outline)
                print("  → 重新生成正文...")
                raw_text, chapter_title = _run_draft(
                    loop,
                    chapter_outline,
                    plot_analysis,
                    plot_data_for_draft,
                    story_history_for_draft,
                    previous_chapter_ending,
                    rewrite_feedback=str(continuity_data.get("review_comments", "")),
                )
            retry_count += 1
            continue

        print("✓ 逻辑检查通过")
        audit_passed = True
        database_updates = continuity_data.get("database_updates") or {}
        if database_updates:
            print("  → 更新数据库状态...")
            if tracker:
                tracker.phase("database_update", "running")
            try:
                loop.db.update(database_updates)
            except Exception as e:
                raise RuntimeError(f"更新数据库时出错，本章不会写入: {e}") from e
            if tracker:
                tracker.phase("database_update", "completed")

    return audit_passed, raw_text, chapter_title, plot_data, plot_data_for_draft


def _build_review_feedback_text(review_data: dict[str, Any]) -> str:
    parts = []
    summary = str(review_data.get("review_summary", "")).strip()
    if summary:
        parts.append(summary)
    for item in review_data.get("toxic_points", []) or []:
        text = str(item).strip()
        if text:
            parts.append(text)
    for item in review_data.get("improvement_suggestions", []) or []:
        text = str(item).strip()
        if text:
            parts.append(text)
    return "\n".join(parts)
def _run_writeback(loop, chapter_title: str, raw_text: str, chapter_outline: dict) -> None:
    print("\n[G] 历史档案馆正在归档...")
    lore_archivist = LoreArchivist(
        chapter_num=loop.current_global_chapter_num,
        chapter_title=chapter_title,
        final_chapter_text=raw_text,
        previous_story_summary=loop.story_memory.get("running_summary", ""),
        recent_story_summaries=_recent_story_summaries_text(loop.story_memory, limit=5),
        active_threads_summary="\n".join(
            f"- {thread.get('description', '')}"
            for thread in loop.story_memory.get("active_threads", [])[:8]
            if isinstance(thread, dict) and thread.get("description")
        ),
        volume_num=loop.current_volume_num,
        volume_plan=loop.volume_plan or {},
        chapter_outline=chapter_outline,
    )
    lore_result = lore_archivist.run()
    if not isinstance(lore_result, dict):
        raise ValueError("LoreArchivist 必须返回 JSON 对象")
    lore_data = lore_result
    _sanitize_lore_roadmap_updates(loop, lore_data)
    lore_text = json.dumps(lore_data, ensure_ascii=False, indent=2)
    loop.lore_records.append(lore_data)

    lore_file = lore_artifact_path(loop.book_dir, loop.current_volume_num, loop.current_chapter_num)
    with open(lore_file, "w", encoding="utf-8") as f:
        f.write(lore_text)
    print(f"✓ 历史记录已保存: {lore_file}")

    plot_threads = lore_data.get("plot_threads", {})
    opened_threads = plot_threads.get("opened", [])
    if opened_threads:
        loop.cliffhanger = opened_threads[-1].get("description", "")
    else:
        loop.cliffhanger = chapter_outline.get("cliffhanger", "")

    loop.story_memory = merge_lore_into_story_memory(
        loop.story_memory,
        lore_data,
        chapter_num=loop.current_global_chapter_num,
        chapter_title=chapter_title,
        volume_num=loop.current_volume_num,
        cliffhanger=loop.cliffhanger,
    )
    write_json_file(story_memory_path(loop.book_dir), loop.story_memory)

    chapter_file = chapter_artifact_path(loop.book_dir, loop.current_volume_num, loop.current_chapter_num)
    with open(chapter_file, "w", encoding="utf-8") as f:
        f.write(f"# {chapter_title}\n\n")
        f.write(raw_text)
    print(f"✓ 章节已保存: {chapter_file}")


def _recent_story_summaries_text(story_memory: dict[str, Any], limit: int) -> str:
    recent = story_memory.get("recent_chapter_summaries", [])[-limit:]
    lines = []
    for item in recent:
        if not isinstance(item, dict):
            continue
        summary = str(item.get("summary_text", "")).strip()
        if summary:
            lines.append(f"第{item.get('chapter_num', '?')}章：{summary}")
    return "\n".join(lines)


def _sanitize_lore_roadmap_updates(loop, lore_data: dict[str, Any]) -> None:
    roadmap = loop.volume_plan.get("roadmap", []) if isinstance(loop.volume_plan, dict) else []
    if not roadmap:
        lore_data["roadmap_updates"] = {"completed_stage_indexes": []}
        return

    progress = build_volume_progress(loop.volume_plan or {}, loop.current_chapter_num)
    current_stage = progress.get("current_stage") if isinstance(progress, dict) else None
    current_stage_index = current_stage.get("stage_index") if isinstance(current_stage, dict) else len(roadmap)
    current_stage_index = _coerce_int(current_stage_index, len(roadmap))
    max_allowed_stage = max(1, min(current_stage_index, len(roadmap)))
    allowed_indexes = set(range(1, max_allowed_stage + 1))

    raw_updates = lore_data.get("roadmap_updates", {})
    raw_indexes = raw_updates.get("completed_stage_indexes", []) if isinstance(raw_updates, dict) else []
    if not isinstance(raw_indexes, list):
        raw_indexes = []

    valid_indexes = sorted(
        {
            value
            for value in (_coerce_int(item, -1) for item in raw_indexes)
            if value in allowed_indexes
        }
    )
    ignored_indexes = sorted(
        {
            value
            for value in (_coerce_int(item, -1) for item in raw_indexes)
            if value > 0 and value not in allowed_indexes
        }
    )
    if ignored_indexes:
        print(f"⚠ 忽略超出当前进度的 roadmap 完成标记: {ignored_indexes}")

    lore_data["roadmap_updates"] = {"completed_stage_indexes": valid_indexes}
