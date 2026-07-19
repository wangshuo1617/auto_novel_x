from __future__ import annotations

import contextlib
import io
import json
import shutil
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from agents import DraftSmith, PlotEngineer
from utils.book_artifacts import (
    chapter_display_name,
    detect_book_title,
    infer_main_story_goal_from_world_setting,
    list_artifact_paths,
    list_book_dirs,
    list_chapter_files,
    parse_chapter_identity,
    list_lore_files,
    list_plot_files,
    list_volume_plan_files,
    load_json_file,
    parse_lore_identity,
    parse_plot_range_identity,
    parse_volume_plan_number,
    plot_arc_artifact_path,
    resolve_relative_path,
    write_json_file,
    write_text_file,
)
from utils.consistency_checker import check_book_consistency
from utils.database import get_database_for_book
from utils.generation_state import list_generation_states, reconcile_stale_generation_state
from utils.llm_logging import list_llm_run_logs
from utils.prompt_presets import (
    DEFAULT_PROMPT_PRESET_ID,
    create_prompt_preset,
    get_prompt_preset_view,
    list_prompt_presets,
    save_prompt_preset_meta,
    save_prompt_template,
    use_prompt_preset,
)
from utils.llm_client import gemini_client, load_prompt_config
from utils.story_context import build_volume_progress, empty_story_memory, merge_lore_into_story_memory, story_context_for_draft, story_context_for_plot
from workflows.phase_initialization import _business_markdown
from workflows.review_utils import is_review_passed, run_reader_review
from workflows.main_loop import MainLoop


BOOK_META_FILE = "book_meta.json"

DATABASE_TABLES: dict[str, dict[str, Any]] = {
    "characters": {
        "label": "角色",
        "primary_key": ["id"],
        "columns": ["id", "name", "type", "data", "created_at", "updated_at"],
        "json_columns": ["data"],
        "readonly_columns": ["created_at", "updated_at"],
        "required_columns": ["id", "name", "type", "data"],
    },
    "character_status": {
        "label": "角色状态",
        "primary_key": ["character_id"],
        "columns": ["character_id", "location_id", "state", "stats"],
        "json_columns": ["stats"],
        "required_columns": ["character_id"],
    },
    "character_inventory": {
        "label": "角色背包",
        "primary_key": ["character_id", "item_id"],
        "columns": ["character_id", "item_id", "quantity"],
        "integer_columns": ["quantity"],
        "required_columns": ["character_id", "item_id"],
        "defaults": {"quantity": 1},
    },
    "character_relations": {
        "label": "角色关系",
        "primary_key": ["character_id", "target_id"],
        "columns": ["character_id", "target_id", "relation", "trust_level"],
        "integer_columns": ["trust_level"],
        "required_columns": ["character_id", "target_id"],
        "defaults": {"trust_level": 50},
    },
    "locations": {
        "label": "地点",
        "primary_key": ["id"],
        "columns": ["id", "name", "type", "description", "data", "created_at"],
        "json_columns": ["data"],
        "readonly_columns": ["created_at"],
        "required_columns": ["id", "name"],
    },
    "items": {
        "label": "物品",
        "primary_key": ["id"],
        "columns": ["id", "name", "type", "rarity", "effect_description", "data", "created_at"],
        "json_columns": ["data"],
        "readonly_columns": ["created_at"],
        "required_columns": ["id", "name"],
    },
    "item_placement": {
        "label": "物品位置",
        "primary_key": ["item_id"],
        "columns": ["item_id", "placement_type", "location_id", "owner_id"],
        "required_columns": ["item_id"],
    },
}


@dataclass(slots=True)
class BookSummary:
    id: str
    title: str
    path: str
    genre: str
    tagline: str
    logline: str
    blurb: str
    chapter_count: int
    volume_count: int
    artifact_count: int
    updated_at: str
    main_story_goal: str
    prompt_preset_id: str
    prompt_preset_name: str


@dataclass(slots=True)
class ActionResult:
    success: bool
    message: str
    logs: str
    payload: dict[str, Any] | None = None


def list_books(output_dir: str | Path = "output") -> list[BookSummary]:
    books: list[BookSummary] = []
    prompt_preset_map = {preset["id"]: preset for preset in list_prompt_presets()}
    for book_dir in list_book_dirs(output_dir):
        reconcile_stale_generation_state(book_dir)
        world_setting = load_json_file(book_dir / "world_setting.json", {})
        business = world_setting.get("business_analysis", {}) if isinstance(world_setting, dict) else {}
        book_meta = _load_book_meta(book_dir)
        prompt_preset_id = str(book_meta.get("prompt_preset_id") or DEFAULT_PROMPT_PRESET_ID)
        prompt_preset = prompt_preset_map.get(prompt_preset_id) or prompt_preset_map.get(DEFAULT_PROMPT_PRESET_ID, {})
        chapter_count = len(list_chapter_files(book_dir))
        volume_count = _volume_count(book_dir)
        books.append(
            BookSummary(
                id=book_dir.name,
                title=detect_book_title(book_dir),
                path=str(book_dir),
                genre=business.get("selected_genre", ""),
                tagline=business.get("tagline", ""),
                logline=business.get("logline", ""),
                blurb=business.get("blurb", ""),
                chapter_count=chapter_count,
                volume_count=volume_count,
                artifact_count=len(list_artifact_paths(book_dir)),
                updated_at=_format_timestamp(book_dir.stat().st_mtime),
                main_story_goal=book_meta.get("main_story_goal", "") or infer_main_story_goal_from_world_setting(world_setting),
                prompt_preset_id=prompt_preset_id,
                prompt_preset_name=str(prompt_preset.get("name", prompt_preset_id)),
            )
        )

    return books


def get_book_view(book_dir: str | Path) -> dict[str, Any]:
    book_path = Path(book_dir)
    reconcile_stale_generation_state(book_path)
    world_setting = load_json_file(book_path / "world_setting.json", {})
    book_meta = _load_book_meta(book_path)
    db = get_database_for_book(book_path)
    db_state = db.get_state()

    chapter_files = list_chapter_files(book_path)
    lore_files = list_lore_files(book_path)
    volume_plan_files = list_volume_plan_files(book_path)
    plot_files = list_plot_files(book_path)
    prompt_preset_id = str(book_meta.get("prompt_preset_id") or DEFAULT_PROMPT_PRESET_ID)
    prompt_presets = list_prompt_presets()
    prompt_preset_map = {preset["id"]: preset for preset in prompt_presets}

    artifact_catalog = {
        "核心设定": [
            name for name in ["world_setting.json", "world_setting.md", BOOK_META_FILE] if (book_path / name).exists()
        ],
        "分卷计划": [path.name for path in volume_plan_files],
        "剧情大纲": [path.name for path in plot_files],
        "章节正文": [path.name for path in chapter_files],
        "历史档案": [path.name for path in lore_files],
        "数据库": ["database.db"] if (book_path / "database.db").exists() else [],
        "弃用产物": ["element_data.json"] if (book_path / "element_data.json").exists() else [],
        "其他产物": _collect_misc_artifacts(book_path),
    }

    return {
        "summary": asdict(_find_book_summary(book_path)),
        "book_meta": book_meta,
        "prompt_preset": prompt_preset_map.get(prompt_preset_id) or prompt_preset_map.get(DEFAULT_PROMPT_PRESET_ID, {}),
        "prompt_presets": prompt_presets,
        "world_setting": world_setting,
        "element_data": db_state,
        "db_state": db_state,
        "artifact_catalog": artifact_catalog,
        "chapter_options": [
            {
                "path": path.name,
                "label": chapter_display_name(path),
            }
            for path in chapter_files
        ],
        "lore_options": [path.name for path in lore_files],
    }


def create_book_with_initialization(
    output_dir: str | Path,
    human_idea: str,
    main_story_goal: str,
    trend_analysis_text: str = "",
    prompt_preset_id: str = DEFAULT_PROMPT_PRESET_ID,
    log_callback: Callable[[str], None] | None = None,
) -> ActionResult:
    trend_analysis = {}
    if trend_analysis_text.strip():
        trend_analysis = json.loads(trend_analysis_text)

    loop = MainLoop(
        output_dir=str(output_dir),
        trend_analysis=trend_analysis,
        human_idea=human_idea.strip(),
        main_story_goal=main_story_goal.strip(),
        prompt_preset_id=prompt_preset_id,
    )
    _save_book_meta(
        loop.book_dir,
        {
            "human_idea": human_idea.strip(),
            "main_story_goal": main_story_goal.strip(),
            "prompt_preset_id": prompt_preset_id,
            "created_at": datetime.now().isoformat(),
        },
    )

    return _capture_action(
        lambda: {
            "book_dir": str(loop.book_dir),
            "initialized": _initialize_loop(loop),
            "title": detect_book_title(loop.book_dir),
            "main_story_goal": loop.main_story_goal,
            "prompt_preset_id": prompt_preset_id,
        },
        message="书籍已创建并完成初始化。",
        log_callback=log_callback,
    )


def run_book_action(
    book_dir: str | Path,
    action: str,
    main_story_goal: str = "",
    chapter_count: int = 1,
    prompt_preset_id: str = "",
    log_callback: Callable[[str], None] | None = None,
) -> ActionResult:
    book_path = Path(book_dir)
    reconcile_stale_generation_state(book_path)
    book_meta = _load_book_meta(book_path)
    world_setting = load_json_file(book_path / "world_setting.json", {})
    selected_prompt_preset_id = prompt_preset_id or str(_load_book_meta(book_path).get("prompt_preset_id") or DEFAULT_PROMPT_PRESET_ID)
    effective_main_story_goal = (
        main_story_goal.strip()
        or str(book_meta.get("main_story_goal", "")).strip()
        or infer_main_story_goal_from_world_setting(world_setting)
    )
    _save_book_meta(
        book_path,
        {"main_story_goal": effective_main_story_goal, "prompt_preset_id": selected_prompt_preset_id},
    )
    loop = MainLoop(
        book_dir_path=str(book_path),
        main_story_goal=effective_main_story_goal,
        prompt_preset_id=selected_prompt_preset_id,
    )

    if action == "generate_chapter":
        return _capture_action(
            lambda: _generate_chapter_and_maybe_start_new_volume(loop),
            message="已生成下一章，并检查当前卷 roadmap 完成状态。",
            log_callback=log_callback,
        )
    if action == "generate_chapters":
        validated_count = _validate_batch_chapter_count(chapter_count)
        return _capture_action(
            lambda: _generate_multiple_chapters(
                book_path,
                main_story_goal=effective_main_story_goal,
                prompt_preset_id=selected_prompt_preset_id,
                chapter_count=validated_count,
            ),
            message=f"已连续生成 {validated_count} 章，并逐章检查卷切换状态。",
            log_callback=log_callback,
        )
    if action == "start_new_volume":
        return _capture_action(lambda: _start_new_volume(loop), message="已开始新卷。", log_callback=log_callback)

    raise ValueError(f"未知动作: {action}")


def list_prompt_preset_summaries() -> list[dict[str, Any]]:
    return list_prompt_presets()


def get_prompt_preset_detail(preset_id: str) -> dict[str, Any]:
    return get_prompt_preset_view(preset_id)


def create_prompt_preset_copy(name: str, description: str = "", source_preset_id: str = DEFAULT_PROMPT_PRESET_ID) -> dict[str, Any]:
    return create_prompt_preset(name=name, description=description, source_preset_id=source_preset_id)


def update_prompt_preset_info(preset_id: str, name: str | None = None, description: str | None = None) -> dict[str, Any]:
    return save_prompt_preset_meta(preset_id, name=name, description=description)


def save_prompt_template_config(preset_id: str, template_name: str, config: dict[str, Any]) -> dict[str, Any]:
    return save_prompt_template(preset_id, template_name, config)


def update_book_prompt_preset(book_dir: str | Path, prompt_preset_id: str) -> None:
    _save_book_meta(book_dir, {"prompt_preset_id": prompt_preset_id})


def delete_book(book_dir: str | Path) -> dict[str, Any]:
    book_path = Path(book_dir).resolve()
    if not book_path.exists():
        raise ValueError(f"书籍目录不存在：{book_path}")
    if not book_path.is_dir():
        raise ValueError(f"书籍路径不是目录：{book_path}")
    if not book_path.name.startswith("book_"):
        raise ValueError(f"仅支持删除 book_* 书籍目录：{book_path.name}")
    if not any((book_path / marker).exists() for marker in ("world_setting.json", BOOK_META_FILE, "database.db")):
        raise ValueError(f"目标目录看起来不是有效书籍目录：{book_path}")

    book_title = detect_book_title(book_path)
    shutil.rmtree(book_path)
    return {"book_dir": str(book_path), "title": book_title}


def read_artifact_text(book_dir: str | Path, relative_path: str) -> str:
    artifact_path = resolve_relative_path(book_dir, relative_path)
    with open(artifact_path, "r", encoding="utf-8") as f:
        return f.read()


def save_artifact_text(book_dir: str | Path, relative_path: str, content: str) -> None:
    artifact_path = resolve_relative_path(book_dir, relative_path)
    if artifact_path.suffix == ".json":
        parsed = json.loads(content)
        write_json_file(artifact_path, parsed)
        return
    write_text_file(artifact_path, content)


def regenerate_artifact(
    book_dir: str | Path,
    relative_path: str,
    prompt_preset_id: str = "",
    log_callback: Callable[[str], None] | None = None,
) -> ActionResult:
    book_path = Path(book_dir)
    selected_prompt_preset_id = prompt_preset_id or str(
        _load_book_meta(book_path).get("prompt_preset_id") or DEFAULT_PROMPT_PRESET_ID
    )
    return _capture_action(
        lambda: _regenerate_artifact(book_path, relative_path, selected_prompt_preset_id),
        message=f"已重生成 {relative_path}。",
        log_callback=log_callback,
    )


def get_book_health_report(book_dir: str | Path) -> dict[str, Any]:
    return check_book_consistency(book_dir)


def get_generation_state_history(book_dir: str | Path, limit: int = 20) -> list[dict[str, Any]]:
    return list_generation_states(book_dir, limit=limit)


def get_llm_run_log_history(book_dir: str | Path, limit: int = 20) -> list[dict[str, Any]]:
    return list_llm_run_logs(book_dir, limit=limit)


def list_database_tables(book_dir: str | Path) -> list[dict[str, Any]]:
    db = get_database_for_book(book_dir)
    rows = []
    for table_name, schema in DATABASE_TABLES.items():
        cursor = db.conn.execute(f"SELECT COUNT(*) AS count FROM {table_name}")
        count = cursor.fetchone()["count"]
        rows.append(
            {
                "name": table_name,
                "label": schema["label"],
                "row_count": count,
                "primary_key": schema["primary_key"],
            }
        )
    return rows


def get_database_table(book_dir: str | Path, table_name: str) -> dict[str, Any]:
    schema = _database_table_schema(table_name)
    db = get_database_for_book(book_dir)
    order_by = ", ".join(schema["primary_key"])
    cursor = db.conn.execute(f"SELECT {', '.join(schema['columns'])} FROM {table_name} ORDER BY {order_by}")
    rows = [dict(row) for row in cursor.fetchall()]
    return {
        "name": table_name,
        "label": schema["label"],
        "columns": schema["columns"],
        "primary_key": schema["primary_key"],
        "json_columns": schema.get("json_columns", []),
        "integer_columns": schema.get("integer_columns", []),
        "readonly_columns": schema.get("readonly_columns", []),
        "required_columns": schema.get("required_columns", []),
        "rows": rows,
    }


def save_database_table(book_dir: str | Path, table_name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    schema = _database_table_schema(table_name)
    db = get_database_for_book(book_dir)
    normalized_rows = [
        _normalize_database_row(schema, row)
        for row in rows
        if _row_has_any_value(row, schema["columns"])
    ]

    pk_columns = schema["primary_key"]
    writable_columns = [column for column in schema["columns"] if column not in schema.get("readonly_columns", [])]
    existing_keys = _database_primary_keys(db, table_name, pk_columns)
    incoming_keys = {_row_key(row, pk_columns) for row in normalized_rows}
    delete_keys = existing_keys - incoming_keys
    _validate_database_deletes(db, table_name, pk_columns, delete_keys)
    _validate_database_rows(table_name, normalized_rows)

    with db.conn:
        if table_name == "character_inventory":
            _replace_character_inventory_rows(db, normalized_rows)
        elif table_name == "item_placement":
            _replace_item_placement_rows(db, normalized_rows)
        else:
            for key in delete_keys:
                _delete_database_row(db, table_name, pk_columns, key)
            for row in normalized_rows:
                _upsert_database_row(db, table_name, pk_columns, writable_columns, row)

    return {
        "saved_rows": len(normalized_rows),
        "deleted_rows": len(delete_keys),
    }


def _database_table_schema(table_name: str) -> dict[str, Any]:
    if table_name not in DATABASE_TABLES:
        raise ValueError(f"不支持编辑数据表: {table_name}")
    schema = dict(DATABASE_TABLES[table_name])
    schema["name"] = table_name
    return schema


def is_regeneratable_artifact(relative_path: str) -> bool:
    """True when _regenerate_artifact supports this path."""
    if relative_path in ("world_setting.json", "world_setting.md"):
        return True
    if parse_chapter_identity(relative_path) is not None:
        return True
    return parse_plot_range_identity(relative_path) is not None


def _regenerate_artifact(book_path: Path, relative_path: str, prompt_preset_id: str) -> dict[str, Any]:
    if relative_path == "world_setting.json":
        return _regenerate_world_setting(book_path, prompt_preset_id)
    if relative_path == "world_setting.md":
        return _rebuild_world_setting_markdown(book_path)
    chapter_identity = parse_chapter_identity(relative_path)
    if chapter_identity:
        return _regenerate_chapter_markdown(book_path, relative_path, prompt_preset_id)
    if parse_plot_range_identity(relative_path):
        return _regenerate_plot_arc(book_path, relative_path, prompt_preset_id)
    raise ValueError(f"暂不支持自动重生成该产物：{relative_path}")


def _regenerate_plot_arc(book_path: Path, relative_path: str, prompt_preset_id: str) -> dict[str, Any]:
    plot_file = resolve_relative_path(book_path, relative_path)
    identity = parse_plot_range_identity(plot_file)
    if identity is None:
        raise ValueError(f"无法识别剧情大纲文件：{relative_path}")
    volume_num, start_chapter, _ = identity

    world_setting = load_json_file(book_path / "world_setting.json", {})
    if not isinstance(world_setting, dict) or not world_setting:
        raise ValueError("缺少 world_setting.json，无法重生成剧情大纲")
    novel_setting = world_setting.get("novel_setting", {})
    db_state = get_database_for_book(book_path).get_state()

    volume_plan: dict = {}
    for vf in list_volume_plan_files(book_path):
        if parse_volume_plan_number(vf) == volume_num:
            volume_plan = load_json_file(vf, {})
            break

    story_memory, lore_records = _rebuild_story_memory_before_chapter(book_path, volume_num, start_chapter)
    story_history = story_context_for_plot(story_memory)
    volume_progress = build_volume_progress(volume_plan, start_chapter)

    print(f"正在重生成第 {volume_num} 卷第 {start_chapter} 章起的剧情大纲...")
    with use_prompt_preset(prompt_preset_id):
        plot_result = PlotEngineer(
            world_setting=novel_setting,
            db_state=db_state,
            story_history=story_history,
            volume_plan=volume_plan,
            volume_progress=volume_progress,
            current_chapter_num=start_chapter,
        ).run()

    if not isinstance(plot_result, dict):
        raise ValueError("PlotEngineer 必须返回 JSON 对象")
    plot_arc = plot_result.get("plot_arc") or []
    if not plot_arc:
        raise ValueError("PlotEngineer 返回了空大纲")

    for i, entry in enumerate(plot_arc):
        if isinstance(entry, dict):
            entry["chapter_num"] = start_chapter + i

    plot_result["volume_num"] = volume_num
    plot_result["volume_progress"] = volume_progress
    write_json_file(plot_file, plot_result)
    return {"artifact": relative_path}


def _regenerate_world_setting(book_path: Path, prompt_preset_id: str) -> dict[str, Any]:
    current_world_setting = load_json_file(book_path / "world_setting.json", {})
    if not isinstance(current_world_setting, dict) or not current_world_setting:
        raise ValueError("缺少可用于重生成的 world_setting.json")

    book_meta = _load_book_meta(book_path)
    with use_prompt_preset(prompt_preset_id):
        system_prompt = load_prompt_config("world_architect_prompt", "system")
        response_schema = load_prompt_config("world_architect_prompt", "json_schema")

    current_title = ((current_world_setting.get("business_analysis") or {}).get("book_title") or "").strip()
    user_prompt = f"""
# Context
你正在重生成一本已存在小说的总纲。目标不是推翻它，而是在保留核心 premise、人物关系、世界观底盘和商业方向的前提下，输出符合当前提示词要求的完整新版总纲。

## 已有 book_meta
{json.dumps(book_meta, ensure_ascii=False, indent=2)}

## 当前总纲（必须优先保留）
{json.dumps(current_world_setting, ensure_ascii=False, indent=2)}

# Task
请基于当前总纲做“保守升级”，输出完整 JSON：
1. 尽量保留现有书名、题材、核心关系、世界观逻辑、独特卖点与情绪基调。
2. 如果当前总纲缺少新 schema 要求的字段，必须补齐，尤其是 `ending_blueprint`。
3. 如果当前内容与现行提示词冲突，只做最小必要改写，不要把整本书改成另一套 premise。
4. 如果已有书名质量足够好，默认保留原书名：{current_title or "（如无则自行拟定）"}。
5. 不要把自伤、轻生、跳崖、拿命威胁他人写成核心卖点、关系推进器或终局高光。

# Output
严格按照当前 schema 输出完整 JSON，不要附加解释。
""".strip()

    result = gemini_client(system_prompt, user_prompt, response_schema)
    if not isinstance(result, dict):
        raise ValueError("重生成的 world_setting 必须是 JSON 对象")

    write_json_file(book_path / "world_setting.json", result)
    novel_setting = result.get("novel_setting", {})
    write_text_file(book_path / "world_setting.md", _business_markdown(result.get("business_analysis", {}), novel_setting))
    return {"artifact": "world_setting.json", "book_title": detect_book_title(book_path)}


def _rebuild_world_setting_markdown(book_path: Path) -> dict[str, Any]:
    world_setting = load_json_file(book_path / "world_setting.json", {})
    if not isinstance(world_setting, dict) or not world_setting:
        raise ValueError("缺少 world_setting.json，无法重生成 world_setting.md")
    novel_setting = world_setting.get("novel_setting", {})
    write_text_file(book_path / "world_setting.md", _business_markdown(world_setting.get("business_analysis", {}), novel_setting))
    return {"artifact": "world_setting.md"}


def _regenerate_chapter_markdown(book_path: Path, relative_path: str, prompt_preset_id: str) -> dict[str, Any]:
    chapter_path = resolve_relative_path(book_path, relative_path)
    chapter_identity = parse_chapter_identity(chapter_path)
    if chapter_identity is None:
        raise ValueError(f"无法识别章节产物：{relative_path}")
    volume_num, chapter_num = chapter_identity

    world_setting = load_json_file(book_path / "world_setting.json", {})
    if not isinstance(world_setting, dict) or not world_setting:
        raise ValueError("缺少 world_setting.json，无法重生成章节")
    novel_setting = world_setting.get("novel_setting", {})
    if not isinstance(novel_setting, dict) or not novel_setting:
        raise ValueError("world_setting.json 缺少 novel_setting，无法重生成章节")

    chapter_outline, plot_analysis, plot_data = _load_chapter_outline_for_regeneration(book_path, volume_num, chapter_num)
    db_state = get_database_for_book(book_path).get_state()
    story_memory, prior_lore_records = _rebuild_story_memory_before_chapter(book_path, volume_num, chapter_num)
    story_history_for_draft = story_context_for_draft(story_memory, prior_lore_records)
    previous_chapter_ending = _extract_chapter_hook(_load_previous_chapter_ending(book_path, volume_num, chapter_num)) if _load_previous_chapter_ending(book_path, volume_num, chapter_num) else ""
    plot_data_for_draft = _build_plot_data_for_draft_from_outline(db_state, chapter_outline)

    print(f"正在重生成第 {volume_num} 卷第 {chapter_num} 章...")
    later_chapters = [
        path for path in list_chapter_files(book_path)
        if (identity := parse_chapter_identity(path)) and identity > (volume_num, chapter_num)
    ]
    if later_chapters:
        print("⚠ 当前仅重写该章节 Markdown，不会自动重算后续章节、lore 或 story_memory。")

    last_review: dict[str, Any] = {}
    raw_text = ""
    chapter_title = f"第{chapter_num}章"

    with use_prompt_preset(prompt_preset_id):
        for attempt in range(3):
            rewrite_feedback = ""
            if last_review and attempt > 0:
                rewrite_feedback = "\n".join(last_review.get("improvement_suggestions", []))
            raw_text, chapter_title = _draft_chapter_markdown(
                novel_setting=novel_setting,
                db_state=db_state,
                story_history_for_draft=story_history_for_draft,
                previous_chapter_ending=previous_chapter_ending,
                plot_analysis=plot_analysis,
                plot_data_for_draft=plot_data_for_draft,
                chapter_num=chapter_num,
                rewrite_feedback=rewrite_feedback,
            )
            last_review = run_reader_review(
                review_stage="chapter_draft",
                content_to_review=raw_text,
                context_payload={
                    "chapter_outline": chapter_outline,
                    "plot_analysis": plot_analysis,
                    "plot_data": plot_data,
                    "story_context": story_history_for_draft,
                    "previous_chapter_ending": previous_chapter_ending,
                    "chapter_cliffhanger": chapter_outline.get("cliffhanger", ""),
                },
                evaluation_focus="检查重生成章节是否兑现当前章大纲、承接前文，并修复当前用户指出的人物与关系问题。",
            ) or {"decision": "PASS", "score": 3}
            score = _coerce_int(last_review.get("score", 3), 3)
            char_count = sum(1 for c in raw_text if not c.isspace())
            if is_review_passed(last_review) and char_count >= 3000:
                print(f"✓ 章节审核通过 (评分: {score}/5, 字数≈{char_count})")
                break
            if char_count < 3000 and attempt < 2:
                wc_note = f"\n字数不足（当前约{char_count}字），请将正文扩充至3300-3800字。"
                rewrite_feedback = "\n".join(last_review.get("improvement_suggestions", [])) + wc_note
                # skip the outer rewrite_feedback assignment next iteration
                last_review = {}
                raw_text, chapter_title = _draft_chapter_markdown(
                    novel_setting=novel_setting,
                    db_state=db_state,
                    story_history_for_draft=story_history_for_draft,
                    previous_chapter_ending=previous_chapter_ending,
                    plot_analysis=plot_analysis,
                    plot_data_for_draft=plot_data_for_draft,
                    chapter_num=chapter_num,
                    rewrite_feedback=rewrite_feedback,
                )
                char_count = sum(1 for c in raw_text if not c.isspace())
                print(f"  字数扩充后≈{char_count}")
                break
            print(f"⚠ 章节审核未通过（尝试 {attempt + 1}/3）：{last_review.get('review_summary', '无反馈')}")
        else:
            raise RuntimeError(f"章节重生成失败：{last_review.get('review_summary', '审核未通过')}")

    write_text_file(chapter_path, f"# {chapter_title}\n\n{raw_text}")
    print(f"✓ 章节已重生成: {chapter_path.name}")
    return {
        "artifact": relative_path,
        "title": chapter_title,
        "volume_num": volume_num,
        "chapter_num": chapter_num,
        "scope": "chapter_markdown_only",
    }


def _load_chapter_outline_for_regeneration(book_path: Path, volume_num: int, chapter_num: int) -> tuple[dict[str, Any], str, dict[str, Any]]:
    for plot_file in list_plot_files(book_path):
        identity = parse_plot_range_identity(plot_file)
        if not identity:
            continue
        file_volume, start_chapter, end_chapter = identity
        if file_volume != volume_num or not start_chapter <= chapter_num <= end_chapter:
            continue
        plot_data = load_json_file(plot_file, {})
        if not isinstance(plot_data, dict):
            break
        plot_arc = plot_data.get("plot_arc", []) or []
        for outline in plot_arc:
            if isinstance(outline, dict) and outline.get("chapter_num") == chapter_num:
                return outline, str(plot_data.get("plot_analysis", "")), plot_data
        raise ValueError(f"{plot_file.name} 中缺少第 {chapter_num} 章大纲")
    raise ValueError(f"未找到可用于重生成第 {volume_num} 卷第 {chapter_num} 章的 plot_arc 缓存")


def _rebuild_story_memory_before_chapter(book_path: Path, volume_num: int, chapter_num: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    story_memory = empty_story_memory()
    lore_records: list[dict[str, Any]] = []
    global_chapter_num = 0

    for lore_file in list_lore_files(book_path):
        identity = parse_lore_identity(lore_file)
        if not identity:
            continue
        lore_volume, lore_chapter = identity
        if (lore_volume, lore_chapter) >= (volume_num, chapter_num):
            break
        lore_data = load_json_file(lore_file, {})
        if not isinstance(lore_data, dict):
            continue
        global_chapter_num += 1
        lore_records.append(lore_data)
        story_memory = merge_lore_into_story_memory(
            story_memory,
            lore_data,
            chapter_num=global_chapter_num,
            chapter_title=f"第{global_chapter_num}章",
            volume_num=lore_volume,
        )

    return story_memory, lore_records


def _extract_chapter_hook(text: str) -> str:
    import re
    text = re.sub(r"^#.*\n", "", text).strip()
    sentences = re.split(r"(?<=[。！？…\u201d\u300d\u300f])", text)
    for sent in reversed(sentences):
        sent = sent.strip()
        if len(sent) >= 8:
            return f"[前章钩子: \"{sent[-80:]}\"]"
    return f"[前章钩子: \"{text[-60:]}\"]"


def _load_previous_chapter_ending(book_path: Path, volume_num: int, chapter_num: int, max_chars: int = 600) -> str:
    chapter_files = list_chapter_files(book_path)
    previous_file: Path | None = None
    for chapter_file in chapter_files:
        identity = parse_chapter_identity(chapter_file)
        if identity and identity < (volume_num, chapter_num):
            previous_file = chapter_file
        elif identity and identity >= (volume_num, chapter_num):
            break
    if previous_file is None:
        return ""
    try:
        content = previous_file.read_text(encoding="utf-8").strip()
    except Exception:
        return ""
    return content[-max_chars:] if content else ""


def _build_plot_data_for_draft_from_outline(db_state: dict[str, Any], chapter_outline: dict[str, Any]) -> dict[str, Any]:
    protagonist = db_state.get("protagonist", {}) or {}
    supporting_characters = db_state.get("supporting_characters", []) or []
    villains = db_state.get("villains", []) or []
    participating_characters = []

    if protagonist:
        participating_characters.append(protagonist)

    for char_id in chapter_outline.get("participating_characters", []) or []:
        for char in [*supporting_characters, *villains]:
            if isinstance(char, dict) and char.get("id") == char_id:
                participating_characters.append(char)
                break

    return {
        "location_id": chapter_outline.get("location_id", ""),
        "plot_points": chapter_outline.get("plot_points", []) or [],
        "participating_characters": participating_characters,
        "key_items_used": chapter_outline.get("key_items_used", []) or [],
        "chapter_num": chapter_outline.get("chapter_num", 0),
        "expected_reader_reaction": chapter_outline.get("expected_reader_reaction", ""),
        "emotional_tone": chapter_outline.get("emotional_tone", ""),
        "chapter_cliffhanger": chapter_outline.get("cliffhanger", ""),
    }


def _draft_chapter_markdown(
    *,
    novel_setting: dict[str, Any],
    db_state: dict[str, Any],
    story_history_for_draft: str,
    previous_chapter_ending: str,
    plot_analysis: str,
    plot_data_for_draft: dict[str, Any],
    chapter_num: int,
    rewrite_feedback: str = "",
) -> tuple[str, str]:
    print("\n[E] 正文塑造者正在重生成正文...")
    draft_context = story_history_for_draft
    if rewrite_feedback.strip():
        draft_context = f"{draft_context}\n\n本章重写要求：\n{rewrite_feedback.strip()}".strip()

    draft_smith = DraftSmith(
        world_setting=novel_setting,
        db_state=db_state,
        story_history=draft_context,
        previous_chapter_ending=previous_chapter_ending,
        plot_analysis=plot_analysis,
        plot_data=plot_data_for_draft,
    )
    draft_result = draft_smith.run()
    if not isinstance(draft_result, dict):
        raise ValueError("DraftSmith 必须返回 JSON 对象")

    raw_text = str(draft_result.get("draft_content", "")).strip()
    chapter_title = str(draft_result.get("title", f"第{chapter_num}章")).strip() or f"第{chapter_num}章"
    if not raw_text:
        raise ValueError("DraftSmith 返回缺少 draft_content")
    return raw_text, chapter_title


def _row_has_any_value(row: dict[str, Any], columns: list[str]) -> bool:
    return any(not _is_blank_cell(row.get(column)) for column in columns)


def _normalize_database_row(schema: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    normalized = {}
    defaults = schema.get("defaults", {})
    json_columns = set(schema.get("json_columns", []))
    integer_columns = set(schema.get("integer_columns", []))
    for column in schema["columns"]:
        if column in schema.get("readonly_columns", []):
            continue
        value = row.get(column)
        if _is_blank_cell(value):
            value = defaults.get(column)
        if isinstance(value, str):
            value = value.strip()
            if not value:
                value = defaults.get(column)
        if column in json_columns:
            value = _normalize_json_cell(column, value)
        elif column in integer_columns:
            value = _normalize_integer_cell(column, value, defaults.get(column))
        normalized[column] = value
    _sync_json_data_fields(schema, normalized)

    for column in schema.get("required_columns", []):
        value = normalized.get(column)
        if value is None or value == "":
            raise ValueError(f"{schema['label']} 缺少必填字段: {column}")
    return normalized


def _sync_json_data_fields(schema: dict[str, Any], row: dict[str, Any]) -> None:
    table_name = schema["name"]
    if "data" not in row:
        return
    data = json.loads(row["data"] or "{}")
    if not isinstance(data, dict):
        raise ValueError(f"{schema['label']} 的 data 必须是 JSON 对象")

    if table_name == "characters":
        for column in ("id", "name"):
            if column in row:
                data[column] = row[column]
    elif table_name == "locations":
        for column in ("id", "name", "type", "description"):
            if column in row:
                data[column] = row[column]
    elif table_name == "items":
        for column in ("id", "name", "type", "rarity", "effect_description"):
            if column in row:
                data[column] = row[column]

    row["data"] = json.dumps(data, ensure_ascii=False)


def _is_blank_cell(value: Any) -> bool:
    if value is None:
        return True
    try:
        if value != value:
            return True
    except Exception:
        pass
    return isinstance(value, str) and not value.strip()


def _normalize_json_cell(column: str, value: Any) -> str:
    if value is None:
        return "{}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if not isinstance(value, str):
        raise ValueError(f"{column} 必须是 JSON 字符串或对象")
    parsed = json.loads(value)
    return json.dumps(parsed, ensure_ascii=False)


def _normalize_integer_cell(column: str, value: Any, default: int | None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except Exception as exc:
        raise ValueError(f"{column} 必须是整数") from exc


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


def _database_primary_keys(db, table_name: str, pk_columns: list[str]) -> set[tuple[Any, ...]]:
    cursor = db.conn.execute(f"SELECT {', '.join(pk_columns)} FROM {table_name}")
    return {tuple(row[column] for column in pk_columns) for row in cursor.fetchall()}


def _row_key(row: dict[str, Any], pk_columns: list[str]) -> tuple[Any, ...]:
    return tuple(row[column] for column in pk_columns)


def _delete_database_row(db, table_name: str, pk_columns: list[str], key: tuple[Any, ...]) -> None:
    if table_name == "character_inventory":
        db.conn.execute("DELETE FROM item_placement WHERE item_id = ? AND owner_id = ?", (key[1], key[0]))
    elif table_name == "item_placement":
        db.conn.execute("DELETE FROM character_inventory WHERE item_id = ?", (key[0],))
    where_clause = " AND ".join(f"{column} = ?" for column in pk_columns)
    db.conn.execute(f"DELETE FROM {table_name} WHERE {where_clause}", key)


def _upsert_database_row(
    db,
    table_name: str,
    pk_columns: list[str],
    columns: list[str],
    row: dict[str, Any],
) -> None:
    if table_name == "item_placement":
        db._update_item_placement(
            row["item_id"],
            placement_type=row.get("placement_type"),
            owner_id=row.get("owner_id"),
            location_id=row.get("location_id"),
        )
        return

    placeholders = ", ".join("?" for _ in columns)
    update_columns = [column for column in columns if column not in pk_columns]
    update_clause = ", ".join(f"{column} = excluded.{column}" for column in update_columns)
    sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
    if update_clause:
        sql += f" ON CONFLICT({', '.join(pk_columns)}) DO UPDATE SET {update_clause}"
    else:
        sql += f" ON CONFLICT({', '.join(pk_columns)}) DO NOTHING"
    db.conn.execute(sql, [row.get(column) for column in columns])


def _replace_character_inventory_rows(db, rows: list[dict[str, Any]]) -> None:
    db.conn.execute("DELETE FROM character_inventory")
    db.conn.execute("DELETE FROM item_placement WHERE owner_id IS NOT NULL")
    for row in rows:
        db.conn.execute(
            """
            INSERT INTO character_inventory (character_id, item_id, quantity)
            VALUES (?, ?, ?)
            """,
            (row["character_id"], row["item_id"], row.get("quantity") or 1),
        )
        db.conn.execute(
            """
            INSERT OR REPLACE INTO item_placement (item_id, placement_type, location_id, owner_id)
            VALUES (?, 'inventory_item', NULL, ?)
            """,
            (row["item_id"], row["character_id"]),
        )


def _replace_item_placement_rows(db, rows: list[dict[str, Any]]) -> None:
    db.conn.execute("DELETE FROM item_placement")
    db.conn.execute("DELETE FROM character_inventory")
    for row in rows:
        db._update_item_placement(
            row["item_id"],
            placement_type=row.get("placement_type"),
            owner_id=row.get("owner_id"),
            location_id=row.get("location_id"),
        )


def _validate_database_rows(table_name: str, rows: list[dict[str, Any]]) -> None:
    if table_name == "character_inventory":
        item_owners: dict[str, str] = {}
        for row in rows:
            item_id = row["item_id"]
            owner_id = row["character_id"]
            if item_id in item_owners and item_owners[item_id] != owner_id:
                raise ValueError(f"物品 {item_id} 不能同时属于多个角色")
            item_owners[item_id] = owner_id
    if table_name == "item_placement":
        for row in rows:
            if row.get("placement_type") == "inventory_item" and not row.get("owner_id"):
                raise ValueError(f"物品 {row['item_id']} 标记为 inventory_item 时必须填写 owner_id")


def _validate_database_deletes(
    db,
    table_name: str,
    pk_columns: list[str],
    delete_keys: set[tuple[Any, ...]],
) -> None:
    if not delete_keys:
        return
    if table_name == "characters":
        for (character_id,) in delete_keys:
            references = _count_references(
                db,
                [
                    ("character_status", "character_id"),
                    ("character_inventory", "character_id"),
                    ("character_relations", "character_id"),
                    ("character_relations", "target_id"),
                    ("item_placement", "owner_id"),
                ],
                character_id,
            )
            if references:
                raise ValueError(f"角色 {character_id} 仍被引用，不能直接删除：{references}")
    elif table_name == "locations":
        for (location_id,) in delete_keys:
            references = _count_references(
                db,
                [
                    ("character_status", "location_id"),
                    ("item_placement", "location_id"),
                ],
                location_id,
            )
            if references:
                raise ValueError(f"地点 {location_id} 仍被引用，不能直接删除：{references}")
    elif table_name == "items":
        for (item_id,) in delete_keys:
            references = _count_references(
                db,
                [
                    ("character_inventory", "item_id"),
                    ("item_placement", "item_id"),
                ],
                item_id,
            )
            if references:
                raise ValueError(f"物品 {item_id} 仍被引用，不能直接删除：{references}")


def _count_references(db, targets: list[tuple[str, str]], value: Any) -> dict[str, int]:
    references = {}
    for table_name, column_name in targets:
        cursor = db.conn.execute(f"SELECT COUNT(*) AS count FROM {table_name} WHERE {column_name} = ?", (value,))
        count = cursor.fetchone()["count"]
        if count:
            references[f"{table_name}.{column_name}"] = count
    return references


def matching_lore_for_chapter(book_dir: str | Path, chapter_relative_path: str) -> str | None:
    chapter_identity = None
    for chapter_file in list_chapter_files(book_dir):
        if chapter_file.name == chapter_relative_path:
            chapter_identity = chapter_file
            break

    if chapter_identity is None:
        return None

    chapter_name = Path(chapter_relative_path).name
    if chapter_name.startswith("volume_") and "_chapter_" in chapter_name:
        lore_name = chapter_name.replace("_chapter_", "_lore_record_ch").replace(".md", ".json")
        lore_path = Path(book_dir) / lore_name
        if lore_path.exists():
            return lore_path.name

    return None


class _CallbackStream(io.StringIO):
    def __init__(self, callback: Callable[[str], None] | None = None):
        super().__init__()
        self._callback = callback

    def write(self, s: str) -> int:
        written = super().write(s)
        if self._callback:
            self._callback(self.getvalue())
        return written


def _capture_action(func: Callable[[], Any], message: str, log_callback: Callable[[str], None] | None = None) -> ActionResult:
    stream = _CallbackStream(log_callback)
    try:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            payload = func()
    except Exception as exc:
        logs = stream.getvalue()
        trace = traceback.format_exc()
        if logs and not logs.endswith("\n"):
            logs += "\n"
        logs += trace
        return ActionResult(
            success=False,
            message=f"{message}失败：{exc}",
            logs=logs,
            payload=None,
        )

    return ActionResult(
        success=True,
        message=message,
        logs=stream.getvalue(),
        payload=payload if isinstance(payload, dict) else None,
    )


def _initialize_loop(loop: MainLoop) -> bool:
    loop.initialize()
    if loop.main_story_goal:
        _save_book_meta(loop.book_dir, {"main_story_goal": loop.main_story_goal})
    return True


def _start_new_volume(loop: MainLoop) -> dict[str, Any]:
    loop.start_new_volume()
    return {"current_volume_num": loop.current_volume_num}


def _validate_batch_chapter_count(chapter_count: Any) -> int:
    normalized = _coerce_int(chapter_count, 0)
    if normalized < 2 or normalized > 5:
        raise ValueError("手动连续生成章节数必须在 2-5 章之间")
    return normalized


def _generate_chapter_and_maybe_start_new_volume(loop: MainLoop) -> dict[str, Any]:
    prestarted_new_volume = False
    precompleted_volume_num = None
    if loop.check_volume_complete():
        precompleted_volume_num = loop.current_volume_num
        loop.start_new_volume()
        prestarted_new_volume = True

    chapter_payload = loop.generate_chapter()
    completed_volume_num = loop.current_volume_num
    volume_complete = loop.check_volume_complete()
    payload = {
        "chapter": chapter_payload,
        "volume_complete": volume_complete,
        "started_new_volume": prestarted_new_volume,
        "current_volume_num": loop.current_volume_num,
    }
    if prestarted_new_volume:
        payload.update(
            {
                "precompleted_volume_num": precompleted_volume_num,
                "prestarted_new_volume": True,
            }
        )
    if volume_complete:
        loop.start_new_volume()
        payload.update(
            {
                "completed_volume_num": completed_volume_num,
                "started_new_volume": True,
                "current_volume_num": loop.current_volume_num,
            }
        )
    return payload


def _generate_multiple_chapters(
    book_path: Path,
    *,
    main_story_goal: str,
    prompt_preset_id: str,
    chapter_count: int,
) -> dict[str, Any]:
    generated_chapters: list[dict[str, Any]] = []
    volume_transitions: list[dict[str, int]] = []

    for index in range(chapter_count):
        print("\n" + "-" * 60)
        print(f"手动连续生成进度 {index + 1}/{chapter_count}")
        print("-" * 60)
        loop = MainLoop(
            book_dir_path=str(book_path),
            main_story_goal=main_story_goal,
            prompt_preset_id=prompt_preset_id,
        )
        payload = _generate_chapter_and_maybe_start_new_volume(loop)
        chapter_payload = payload.get("chapter", {}) if isinstance(payload, dict) else {}
        if isinstance(chapter_payload, dict):
            generated_chapters.append(chapter_payload)

        if payload.get("prestarted_new_volume"):
            volume_transitions.append(
                {
                    "from_volume_num": int(payload.get("precompleted_volume_num", 0)),
                    "to_volume_num": int(payload.get("current_volume_num", 0)),
                }
            )
        elif payload.get("volume_complete"):
            volume_transitions.append(
                {
                    "from_volume_num": int(payload.get("completed_volume_num", 0)),
                    "to_volume_num": int(payload.get("current_volume_num", 0)),
                }
            )

    return {
        "requested_count": chapter_count,
        "generated_count": len(generated_chapters),
        "chapters": generated_chapters,
        "volume_transitions": volume_transitions,
    }


def _find_book_summary(book_dir: Path) -> BookSummary:
    for summary in list_books(book_dir.parent):
        if Path(summary.path) == book_dir:
            return summary
    return BookSummary(
        id=book_dir.name,
        title=detect_book_title(book_dir),
        path=str(book_dir),
        genre="",
        tagline="",
        logline="",
        blurb="",
        chapter_count=len(list_chapter_files(book_dir)),
        volume_count=_volume_count(book_dir),
        artifact_count=len(list_artifact_paths(book_dir)),
        updated_at=_format_timestamp(book_dir.stat().st_mtime),
        main_story_goal=_load_book_meta(book_dir).get("main_story_goal", "")
        or infer_main_story_goal_from_world_setting(load_json_file(book_dir / "world_setting.json", {})),
        prompt_preset_id=str(_load_book_meta(book_dir).get("prompt_preset_id") or DEFAULT_PROMPT_PRESET_ID),
        prompt_preset_name=_prompt_preset_name(_load_book_meta(book_dir)),
    )


def _collect_misc_artifacts(book_dir: Path) -> list[str]:
    known = {
        "world_setting.json",
        "world_setting.md",
        "element_data.json",
        "database.db",
        BOOK_META_FILE,
    }
    known.update(path.name for path in list_volume_plan_files(book_dir))
    known.update(path.name for path in list_plot_files(book_dir))
    known.update(path.name for path in list_chapter_files(book_dir))
    known.update(path.name for path in list_lore_files(book_dir))

    return [name for name in list_artifact_paths(book_dir) if name not in known]


def _load_book_meta(book_dir: str | Path) -> dict[str, Any]:
    data = load_json_file(Path(book_dir) / BOOK_META_FILE, {})
    return data if isinstance(data, dict) else {}


def _save_book_meta(book_dir: str | Path, updates: dict[str, Any]) -> None:
    if not updates:
        return
    meta = _load_book_meta(book_dir)
    meta.update({key: value for key, value in updates.items() if value not in (None, "")})
    write_json_file(Path(book_dir) / BOOK_META_FILE, meta)


def _prompt_preset_name(book_meta: dict[str, Any]) -> str:
    prompt_preset_id = str(book_meta.get("prompt_preset_id") or DEFAULT_PROMPT_PRESET_ID)
    prompt_preset_map = {preset["id"]: preset for preset in list_prompt_presets()}
    prompt_preset = prompt_preset_map.get(prompt_preset_id) or prompt_preset_map.get(DEFAULT_PROMPT_PRESET_ID, {})
    return str(prompt_preset.get("name", prompt_preset_id))


def _format_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def _volume_count(book_dir: str | Path) -> int:
    volume_plan_count = len(list_volume_plan_files(book_dir))
    chapter_volumes = {
        identity[0]
        for chapter_file in list_chapter_files(book_dir)
        if (identity := parse_chapter_identity(chapter_file))
    }
    return max(volume_plan_count, len(chapter_volumes))


# ─── 细化大纲：预览与带细纲生成 ────────────────────────────────────────────────

def _format_outline_as_template(outline: dict, chapter_num: int, db_state: dict | None = None) -> str:
    """将 plot_arc 条目格式化为可编辑细纲，自然展开 plot_points，不强制固定段落结构。"""
    db_state = db_state or {}

    def resolve_chars(ids):
        names = []
        for cid in ids:
            found = next(
                (c.get("name", cid) for lst in [
                    [db_state.get("protagonist")] if db_state.get("protagonist") else [],
                    db_state.get("supporting_characters", []),
                    db_state.get("villains", []),
                ] for c in lst if c and c.get("id") == cid), cid)
            names.append(found)
        return "、".join(names) if names else "（见大纲）"

    def resolve_loc(lid):
        for loc in db_state.get("locations", []):
            if loc.get("id") == lid:
                return loc.get("name", lid)
        return lid or "（见大纲）"

    def resolve_items(ids):
        names = [next((i.get("name", iid) for i in db_state.get("items", []) if i.get("id") == iid), iid) for iid in ids]
        return "、".join(names) if names else "无"

    title = outline.get("title", f"第{chapter_num}章")
    points = outline.get("plot_points", []) or []
    emotional_tone = outline.get("emotional_tone", "")
    relationship_beat = outline.get("relationship_beat", "")
    cliffhanger = outline.get("cliffhanger", "")
    expected_reaction = outline.get("expected_reader_reaction", "")
    char_names = resolve_chars(outline.get("participating_characters", []))
    loc_name = resolve_loc(outline.get("location_id", ""))
    item_names = resolve_items(outline.get("key_items_used", []))

    lines = [f"第 {chapter_num} 章：{title}"]
    lines.append(f"出场人物：{char_names}  |  场景：{loc_name}  |  道具：{item_names}")
    if emotional_tone:
        lines.append(f"情绪基调：{emotional_tone}")
    if relationship_beat:
        lines.append(f"感情线：{relationship_beat}")
    lines += ["", "── 剧情流程 ──", ""]

    for i, p in enumerate(points, 1):
        beat = p.get("beat", "") if isinstance(p, dict) else str(p)
        subs = p.get("sub_beats", []) if isinstance(p, dict) else []
        wc = p.get("suggested_expansion") if isinstance(p, dict) else None
        wc_hint = f"（约 {wc} 字）" if wc else ""
        lines.append(f"【{i}】{beat} {wc_hint}")
        for s in subs:
            lines.append(f"   · {s}")
        lines.append("")

    if cliffhanger:
        lines += ["── 结尾钩子 ──", cliffhanger, ""]
    if expected_reaction:
        lines.append(f"预期读者反应：{expected_reaction}")
        lines.append("")

    lines += [
        "情绪嗅觉描写（可选）：人名（情绪）：气味",
        "微表情描写（可选）：人名：细节",
        "伏笔埋设（可选）：道具/行为 → 后续呼应",
    ]
    return "\n".join(lines)


def get_chapter_outline_preview(
    book_dir: str | Path,
    prompt_preset_id: str = "",
) -> ActionResult:
    """获取当前待写章节的细化大纲（格式化为可编辑模板文本）。"""
    book_path = Path(book_dir)
    meta = _load_book_meta(book_path)
    goal = str(meta.get("main_story_goal", "")).strip()
    preset = prompt_preset_id or str(meta.get("prompt_preset_id") or DEFAULT_PROMPT_PRESET_ID)

    def _do():
        loop = MainLoop(book_dir_path=str(book_path), main_story_goal=goal, prompt_preset_id=preset)
        from workflows.chapter_pipeline import _ensure_plot_arc
        from utils.story_context import story_context_for_plot
        if not loop.plot_arc or loop.plot_arc_index >= len(loop.plot_arc):
            with use_prompt_preset(preset):
                from utils.llm_logging import use_llm_log_context
                with use_llm_log_context(loop.book_dir, "outline_preview"):
                    _ensure_plot_arc(loop, story_context_for_plot(loop.story_memory))
        if loop.plot_arc and loop.plot_arc_index < len(loop.plot_arc):
            text = _format_outline_as_template(loop.plot_arc[loop.plot_arc_index], loop.current_chapter_num, db_state=loop.db.get_state())
        else:
            text = f"【第{loop.current_chapter_num}章：待填写】\n\n核心事件：\n\n情绪落点与钩子：\n  结尾悬念："
        # 同时检查是否已有保存的 user_override，优先展示
        for plot_file in list_plot_files(book_path):
            identity = parse_plot_range_identity(plot_file)
            if identity and identity[0] == loop.current_volume_num:
                fv, start, end = identity
                if start <= loop.current_chapter_num <= end:
                    data = load_json_file(plot_file, {})
                    for entry in data.get("plot_arc", []):
                        if entry.get("chapter_num") == loop.current_chapter_num and entry.get("user_override"):
                            text = entry["user_override"]
                    break
        return {"outline_text": text, "chapter_num": loop.current_chapter_num}

    return _capture_action(_do, message="细化大纲已生成。")


def generate_chapter_with_outline(
    book_dir: str | Path,
    outline_text: str,
    main_story_goal: str = "",
    prompt_preset_id: str = "",
    log_callback: Callable[[str], None] | None = None,
) -> ActionResult:
    """用用户审定的细化大纲生成下一章正文。"""
    book_path = Path(book_dir)
    meta = _load_book_meta(book_path)
    goal = main_story_goal.strip() or str(meta.get("main_story_goal", "")).strip()
    preset = prompt_preset_id or str(meta.get("prompt_preset_id") or DEFAULT_PROMPT_PRESET_ID)

    def _do():
        loop = MainLoop(book_dir_path=str(book_path), main_story_goal=goal, prompt_preset_id=preset)
        if loop.check_volume_complete():
            loop.start_new_volume()
        chapter_payload = loop.generate_chapter(outline_override=outline_text)
        loop.check_volume_complete()
        return chapter_payload

    return _capture_action(_do, message="已按细化大纲生成下一章。", log_callback=log_callback)


def save_chapter_outline_override(book_dir: str | Path, override_text: str) -> ActionResult:
    """将用户编辑后的细化大纲保存到 plot_arc 文件的对应章节条目中，生成时自动读取。"""
    book_path = Path(book_dir)
    meta = _load_book_meta(book_path)
    goal = str(meta.get("main_story_goal", "")).strip()
    preset = str(meta.get("prompt_preset_id") or DEFAULT_PROMPT_PRESET_ID)

    def _do():
        loop = MainLoop(book_dir_path=str(book_path), main_story_goal=goal, prompt_preset_id=preset)
        ch_num = loop.current_chapter_num
        vol_num = loop.current_volume_num
        for plot_file in list_plot_files(book_path):
            identity = parse_plot_range_identity(plot_file)
            if not identity:
                continue
            fv, start, end = identity
            if fv == vol_num and start <= ch_num <= end:
                data = load_json_file(plot_file, {})
                for entry in data.get("plot_arc", []):
                    if entry.get("chapter_num") == ch_num:
                        entry["user_override"] = override_text.strip()
                        write_json_file(plot_file, data)
                        print(f"✓ 第{ch_num}章细纲修改已保存至 {plot_file.name}")
                        return
                raise ValueError(f"{plot_file.name} 中未找到第{ch_num}章条目")
        raise ValueError(f"未找到覆盖第{ch_num}章的 plot_arc 文件")

    return _capture_action(_do, message="细纲修改已保存。")


WRITING_GUIDELINES_FILE = "writing_guidelines.json"


def _append_writing_guideline(book_path: Path, instruction: str, source_chapter: str = "") -> None:
    """把一条人工修改意见沉淀到书目录，供后续全文写作参考。去重、限量。"""
    instruction = (instruction or "").strip()
    if not instruction:
        return
    path = book_path / WRITING_GUIDELINES_FILE
    data = load_json_file(path, {}) if path.exists() else {}
    if not isinstance(data, dict):
        data = {}
    items = data.get("guidelines") or []
    # 去重：正文相同的意见不重复记录
    if any(isinstance(g, dict) and g.get("instruction") == instruction for g in items):
        return
    items.append({"instruction": instruction, "source_chapter": source_chapter})
    # 只保留最近 30 条，避免无限膨胀
    data["guidelines"] = items[-30:]
    write_json_file(path, data)
    print(f"✓ 已记录人工写作意见到 {WRITING_GUIDELINES_FILE}（当前 {len(data['guidelines'])} 条）")


def load_writing_guidelines_text(book_dir: str | Path) -> str:
    """读取沉淀的人工写作意见，格式化为可注入 DraftSmith 的文本；无则返回空串。"""
    path = Path(book_dir) / WRITING_GUIDELINES_FILE
    if not path.exists():
        return ""
    data = load_json_file(path, {})
    items = data.get("guidelines") if isinstance(data, dict) else None
    if not items:
        return ""
    lines = []
    for g in items:
        if isinstance(g, dict) and g.get("instruction"):
            lines.append(f"- {g['instruction'].strip()}")
    return "\n".join(lines)


def rewrite_chapter_fragment(
    book_dir: str | Path,
    relative_path: str,
    original_fragment: str,
    instruction: str,
    prompt_preset_id: str = "",
    log_callback: Callable[[str], None] | None = None,
) -> ActionResult:
    """局部重写章节中的指定片段，经书评审核后替换回原文。"""
    book_path = Path(book_dir)
    meta = _load_book_meta(book_path)
    preset = prompt_preset_id or str(meta.get("prompt_preset_id") or DEFAULT_PROMPT_PRESET_ID)

    def _do():
        chapter_path = resolve_relative_path(book_path, relative_path)
        full_text = chapter_path.read_text(encoding="utf-8")
        if original_fragment not in full_text:
            raise ValueError("在章节中找不到该片段，请确认粘贴内容与正文完全一致（包含标点和空格）。")

        world_setting = load_json_file(book_path / "world_setting.json", {})
        novel_setting = (world_setting.get("novel_setting") or {})
        db_state = get_database_for_book(book_path).get_state()
        protagonist_name = (db_state.get("protagonist") or {}).get("name", "")

        with use_prompt_preset(preset):
            system_p = load_prompt_config("draft_smith_prompt", "system")
        user_p = (
            f"以下是当前章节的完整正文（供参考文风和前后文）：\n\n{full_text}\n\n"
            f"---\n"
            f"需要重写的片段：\n\n{original_fragment}\n\n"
            f"---\n"
            f"修改意见：{instruction}\n\n"
            f"请仅输出重写后的片段文字，不要包含任何说明或章节标题。"
            f"重写内容必须能无缝替换回原文对应位置，前后衔接自然。"
        )
        schema = {"type": "object", "properties": {"rewritten": {"type": "string"}}, "required": ["rewritten"]}

        max_attempts = 3
        replacement = ""
        for attempt in range(max_attempts):
            print(f"\n[E] 局部重写中...（尝试 {attempt+1}/{max_attempts}）")
            result = gemini_client(system_p, user_p, schema)
            replacement = result.get("rewritten", "").strip()
            if not replacement:
                continue

            print("\n[I] 毒舌书评人正在审核局部重写...")
            review = run_reader_review(
                review_stage="chapter_draft",
                content_to_review=replacement,
                context_payload={"story_context": full_text, "instruction": instruction},
                evaluation_focus="检查局部重写片段是否解决了修改意见，且与上下文衔接自然、风格一致。",
            ) or {"decision": "PASS", "score": 3}
            if is_review_passed(review):
                print(f"✓ 审核通过 (评分: {review.get('score')}/5)")
                break
            print(f"⚠ 审核未通过：{review.get('review_summary','')[:80]}")
            feedback = "\n".join(review.get("improvement_suggestions", []))
            user_p = user_p + f"\n\n上次生成未通过审核，反馈：{feedback}\n请根据反馈重新生成。"
        else:
            print("⚠ 已达最大重试次数，使用最后一次结果")

        if not replacement:
            raise ValueError("重写片段为空，请检查输入。")

        new_text = full_text.replace(original_fragment, replacement, 1)
        write_text_file(chapter_path, new_text)
        print(f"✓ 已替换片段并保存: {chapter_path.name}")

        # 沉淀人工意见：追加到 writing_guidelines.json，供后续全文写作参考，
        # 避免同类问题（如人设台词不符）在新章节反复出现。
        _append_writing_guideline(book_path, instruction, source_chapter=relative_path)
        return {"replaced": True, "chapter": relative_path}

    return _capture_action(_do, message="局部重写完成。", log_callback=log_callback)


# ─── 短故事服务 ─────────────────────────────────────────────────────────────
from workflows.short_story.pipeline import (
    generate_outline as _ss_generate_outline,
    generate_chapter as _ss_generate_chapter,
    list_short_stories as _ss_list,
    get_short_story_view as _ss_view,
)


def list_short_stories_service(output_dir: str | Path = "output") -> list[dict]:
    return _ss_list(output_dir)


def get_short_story_view_service(story_dir: str | Path) -> dict:
    return _ss_view(story_dir)


def create_short_story_outline(
    output_dir: str | Path,
    track: str,
    target_words: int,
    inspiration: str,
    log_callback: Callable[[str], None] | None = None,
) -> ActionResult:
    def _do():
        return _ss_generate_outline(str(output_dir), track, target_words, inspiration)
    return _capture_action(_do, message="大纲已生成。", log_callback=log_callback)


def generate_short_story_chapter(
    story_dir: str | Path,
    chapter_num: int,
    log_callback: Callable[[str], None] | None = None,
) -> ActionResult:
    def _do():
        return _ss_generate_chapter(str(story_dir), chapter_num)
    return _capture_action(_do, message=f"第{chapter_num}章已生成。", log_callback=log_callback)
