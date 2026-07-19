"""
开始新卷：更新卷号、上一卷摘要、分卷导演规划并落盘。
"""

import json
from typing import Any
from agents import ArcDirector, ElementDesigner
from utils.book_artifacts import (
    list_plot_files,
    load_json_file,
    parse_plot_range_identity,
    plot_arc_artifact_path,
    write_json_file,
)
from workflows.review_utils import is_review_passed, run_reader_review


def _trim_orphan_plot_arc(loop) -> None:
    """卷roadmap提前完成（未写满10章批次）时，裁掉本卷 plot_arc 里未写章节的孤儿条目，
    并按实际章号重命名文件，避免与下一卷全局章号冲突（如旧卷 ch11-20 只写到18，
    孤儿 ch19-20 会与新卷第1章的全局第19章错位）。"""
    last_written = loop.current_chapter_num  # 此时是本卷最后写完的章号
    for plot_file in list_plot_files(loop.book_dir):
        identity = parse_plot_range_identity(plot_file)
        if not identity:
            continue
        vol, start, end = identity
        if vol != loop.current_volume_num or end <= last_written:
            continue
        data = load_json_file(plot_file, {})
        if not isinstance(data, dict):
            continue
        arc = [c for c in data.get("plot_arc", []) if c.get("chapter_num", 0) <= last_written]
        if not arc:
            # 整个批次都没写 → 删除空孤儿文件
            plot_file.unlink(missing_ok=True)
            print(f"✓ 删除未使用的孤儿 plot_arc: {plot_file.name}")
            continue
        data["plot_arc"] = arc
        new_start = arc[0].get("chapter_num", start)
        new_end = arc[-1].get("chapter_num", last_written)
        new_file = plot_arc_artifact_path(loop.book_dir, vol, new_start, new_end)
        write_json_file(new_file, data)
        if new_file.name != plot_file.name:
            plot_file.unlink(missing_ok=True)
            print(f"✓ 裁剪孤儿章：{plot_file.name} → {new_file.name}")


def run_new_volume(loop) -> None:
    """开始新的一卷：更新卷号与摘要，调用分卷导演规划新卷并保存。"""
    print("\n" + "=" * 60)
    print(f"开始第 {loop.current_volume_num + 1} 卷")
    print("=" * 60)

    # 卷提前收尾时，先裁掉本卷 plot_arc 里未写的孤儿章，防止与新卷全局章号错位
    _trim_orphan_plot_arc(loop)

    if loop.story_memory.get("running_summary"):
        loop.previous_volume_summary = loop.story_memory["running_summary"]

    loop.current_volume_num += 1
    loop.current_chapter_num = 1
    loop.plot_arc = []
    loop.plot_arc_index = 0

    print("\n[F] 分卷导演正在规划新卷...")
    review_data = {}
    feedback_text = ""
    for attempt in range(3):
        arc_director = ArcDirector(
            world_setting=loop.get_novel_setting(),
            db_state=loop.db.get_state(),
            main_story_goal=loop.main_story_goal,
            previous_volume_summary=loop.previous_volume_summary,
            volume_num=loop.current_volume_num,
            review_feedback=feedback_text,
        )
        volume_result = arc_director.run()
        if not isinstance(volume_result, dict):
            raise ValueError("ArcDirector 必须返回 JSON 对象")
        loop.volume_plan = volume_result
        review_data = run_reader_review(
            review_stage="volume_plan",
            content_to_review=loop.volume_plan,
            context_payload={
                "world_setting": loop.get_novel_setting(),
                "db_state": loop.db.get_state(),
                "main_story_goal": loop.main_story_goal,
                "previous_volume_summary": loop.previous_volume_summary,
                "volume_num": loop.current_volume_num,
            },
            evaluation_focus="检查新卷规划是否承接上一卷结果，并为下一卷提供足够清晰的路线图。",
        )
        if is_review_passed(review_data):
            break
        feedback_text = "\n".join(review_data.get("improvement_suggestions", []))
        print(f"⚠ 新卷规划审核未通过（尝试 {attempt + 1}/3）：{review_data.get('review_summary', '无反馈')}")
    else:
        raise RuntimeError(f"新卷规划审核未通过：{review_data.get('review_summary', '无反馈')}")

    volume_file = loop.book_dir / f"volume_{loop.current_volume_num}_plan.json"
    with open(volume_file, "w", encoding="utf-8") as f:
        json.dump(loop.volume_plan, f, ensure_ascii=False, indent=2)
    print(f"✓ 新卷计划已保存: {volume_file}")

    _run_volume_asset_addon(loop)


def _run_volume_asset_addon(loop) -> None:
    print("\n[B+] 元素设计师正在扩展新卷资产...")
    review_data = {}
    feedback_text = ""
    addon_raw: dict[str, Any] = {}
    normalized_assets: dict[str, Any] = {}
    db_state = loop.db.get_state()

    for attempt in range(3):
        element_designer = ElementDesigner(loop.get_novel_setting())
        addon_result = element_designer.run(
            mode="addon",
            request_payload=_build_volume_addon_prompt_payload(loop, db_state),
            review_feedback=feedback_text,
        )
        if not isinstance(addon_result, dict):
            raise ValueError("ElementDesigner addon 必须返回 JSON 对象")
        addon_raw = addon_result
        normalized_assets = _normalize_addon_assets(addon_raw, loop.volume_plan or {})
        review_data = run_reader_review(
            review_stage="element_design",
            content_to_review=addon_raw,
            context_payload={
                "world_setting": loop.get_novel_setting(),
                "db_state": db_state,
                "volume_plan": loop.volume_plan or {},
                "volume_num": loop.current_volume_num,
            },
            evaluation_focus="检查新卷新增地点、角色和资源是否与卷计划、当前战力和既有资产匹配，并能支撑后续剧情展开。",
        )
        if is_review_passed(review_data):
            break
        feedback_text = "\n".join(review_data.get("improvement_suggestions", []))
        print(f"⚠ 新卷资产审核未通过（尝试 {attempt + 1}/3）：{review_data.get('review_summary', '无反馈')}")
    else:
        raise RuntimeError(f"新卷资产审核未通过：{review_data.get('review_summary', '无反馈')}")

    addon_file = loop.book_dir / f"volume_{loop.current_volume_num}_element_addon.json"
    write_json_file(addon_file, addon_raw)
    print(f"✓ 新卷新增资产已保存: {addon_file}")

    if any(normalized_assets.get(key) for key in ("supporting_characters", "villains", "locations", "items")):
        loop.db.merge_element_data(normalized_assets)
        print("✓ 新卷资产已写入数据库")
    else:
        print("⚠ 新卷资产扩展未产出可入库的角色/地点/物品，已仅保留原始产物")


def _build_volume_addon_prompt_payload(loop, db_state: dict[str, Any]) -> dict[str, Any]:
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
        "goal": "为新卷批量生成能直接支撑接下来 10-30 章剧情的新地点、关键角色和资源。",
        "volume_title": loop.volume_plan.get("volume_title", ""),
        "theme_keywords": loop.volume_plan.get("theme_keywords", []),
        "main_villain_id": loop.volume_plan.get("main_villain_id", ""),
        "roadmap": loop.volume_plan.get("roadmap", []),
        "forbidden_plots": loop.volume_plan.get("forbidden_plots", []),
        "protagonist_status": protagonist_status,
        "known_locations": [loc.get("name", "") for loc in db_state.get("locations", [])[:12]],
        "known_supporting_characters": [char.get("name", "") for char in db_state.get("supporting_characters", [])[:12]],
        "known_villains": [char.get("name", "") for char in db_state.get("villains", [])[:12]],
        "known_items": [item.get("name", "") for item in db_state.get("items", [])[:12]],
        "requirements": [
            "优先生成与本卷 roadmap 中新地图、新冲突、新资源直接相关的资产。",
            "至少生成 1 个可承载本卷主冲突的对立角色，必要时补 1-2 个功能型配角。",
            "避免与已有角色、地点、物品重名或 ID 冲突。",
        ],
    }
    return {
        "world_setting_summary": _build_world_setting_summary(loop.get_novel_setting()),
        "current_power_level": current_power_level,
        "existing_assets_summary": _build_existing_assets_summary(db_state),
        "task_mode": "NEW_VOLUME_BATCH",
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


def _normalize_addon_assets(addon_raw: dict[str, Any], volume_plan: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "supporting_characters": [],
        "villains": [],
        "locations": [],
        "items": [],
    }
    if not isinstance(addon_raw, dict):
        return normalized

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

    main_villain_id = str(volume_plan.get("main_villain_id", "")).strip()
    for char in addon_raw.get("new_characters", []) or []:
        char_id = str(char.get("id", "")).strip()
        if not char_id:
            continue
        current_status = {
            "stats": char.get("stats", {}) or {},
            "state": "active",
            "location_id": _resolve_location_id(char.get("initial_location_id"), new_location_ids),
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
                    "type": "world_object",
                    "location_id": _resolve_location_id(item.get("location_id"), new_location_ids),
                    "owner_id": None,
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

