from __future__ import annotations

import contextlib
import io
import json
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from utils.book_artifacts import (
    chapter_display_name,
    detect_book_title,
    list_artifact_paths,
    list_book_dirs,
    list_chapter_files,
    parse_chapter_identity,
    list_lore_files,
    list_plot_files,
    list_volume_plan_files,
    load_json_file,
    resolve_relative_path,
    write_json_file,
    write_text_file,
)
from utils.consistency_checker import check_book_consistency
from utils.database import get_database_for_book
from utils.generation_state import list_generation_states
from utils.llm_logging import list_llm_run_logs
from utils.prompt_presets import (
    DEFAULT_PROMPT_PRESET_ID,
    create_prompt_preset,
    get_prompt_preset_view,
    list_prompt_presets,
    save_prompt_preset_meta,
    save_prompt_template,
)
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
    logline: str
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
                logline=business.get("logline", ""),
                chapter_count=chapter_count,
                volume_count=volume_count,
                artifact_count=len(list_artifact_paths(book_dir)),
                updated_at=_format_timestamp(book_dir.stat().st_mtime),
                main_story_goal=book_meta.get("main_story_goal", ""),
                prompt_preset_id=prompt_preset_id,
                prompt_preset_name=str(prompt_preset.get("name", prompt_preset_id)),
            )
        )

    return books


def get_book_view(book_dir: str | Path) -> dict[str, Any]:
    book_path = Path(book_dir)
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
            "prompt_preset_id": prompt_preset_id,
        },
        message="书籍已创建并完成初始化。",
        log_callback=log_callback,
    )


def run_book_action(
    book_dir: str | Path,
    action: str,
    main_story_goal: str = "",
    prompt_preset_id: str = "",
    log_callback: Callable[[str], None] | None = None,
) -> ActionResult:
    book_path = Path(book_dir)
    selected_prompt_preset_id = prompt_preset_id or str(_load_book_meta(book_path).get("prompt_preset_id") or DEFAULT_PROMPT_PRESET_ID)
    _save_book_meta(book_path, {"main_story_goal": main_story_goal.strip(), "prompt_preset_id": selected_prompt_preset_id})
    loop = MainLoop(
        book_dir_path=str(book_path),
        main_story_goal=main_story_goal.strip(),
        prompt_preset_id=selected_prompt_preset_id,
    )

    if action == "generate_chapter":
        return _capture_action(
            lambda: _generate_chapter_and_maybe_start_new_volume(loop),
            message="已生成下一章，并检查当前卷 roadmap 完成状态。",
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
    return True


def _start_new_volume(loop: MainLoop) -> dict[str, Any]:
    loop.start_new_volume()
    return {"current_volume_num": loop.current_volume_num}


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


def _find_book_summary(book_dir: Path) -> BookSummary:
    for summary in list_books(book_dir.parent):
        if Path(summary.path) == book_dir:
            return summary
    return BookSummary(
        id=book_dir.name,
        title=detect_book_title(book_dir),
        path=str(book_dir),
        genre="",
        logline="",
        chapter_count=len(list_chapter_files(book_dir)),
        volume_count=_volume_count(book_dir),
        artifact_count=len(list_artifact_paths(book_dir)),
        updated_at=_format_timestamp(book_dir.stat().st_mtime),
        main_story_goal=_load_book_meta(book_dir).get("main_story_goal", ""),
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
