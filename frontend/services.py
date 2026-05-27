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
from utils.database import get_database_for_book
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
    element_data = load_json_file(book_path / "element_data.json", {})
    book_meta = _load_book_meta(book_path)
    db = get_database_for_book(book_path)

    chapter_files = list_chapter_files(book_path)
    lore_files = list_lore_files(book_path)
    volume_plan_files = list_volume_plan_files(book_path)
    plot_files = list_plot_files(book_path)
    prompt_preset_id = str(book_meta.get("prompt_preset_id") or DEFAULT_PROMPT_PRESET_ID)
    prompt_presets = list_prompt_presets()
    prompt_preset_map = {preset["id"]: preset for preset in prompt_presets}

    artifact_catalog = {
        "核心设定": [
            name for name in ["world_setting.json", "world_setting.md", "element_data.json", BOOK_META_FILE] if (book_path / name).exists()
        ],
        "分卷计划": [path.name for path in volume_plan_files],
        "剧情大纲": [path.name for path in plot_files],
        "章节正文": [path.name for path in chapter_files],
        "历史档案": [path.name for path in lore_files],
        "数据库": ["database.db"] if (book_path / "database.db").exists() else [],
        "其他产物": _collect_misc_artifacts(book_path),
    }

    return {
        "summary": asdict(_find_book_summary(book_path)),
        "book_meta": book_meta,
        "prompt_preset": prompt_preset_map.get(prompt_preset_id) or prompt_preset_map.get(DEFAULT_PROMPT_PRESET_ID, {}),
        "prompt_presets": prompt_presets,
        "world_setting": world_setting,
        "element_data": element_data,
        "db_state": db.get_state(),
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
        return _capture_action(loop.generate_chapter, message="已生成下一章。", log_callback=log_callback)
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


def database_state_text(book_dir: str | Path) -> str:
    db = get_database_for_book(book_dir)
    return json.dumps(db.get_state(), ensure_ascii=False, indent=2)


def replace_database_state(book_dir: str | Path, content: str) -> None:
    snapshot = json.loads(content)
    if not isinstance(snapshot, dict):
        raise ValueError("数据库状态必须是 JSON 对象")

    db = get_database_for_book(book_dir)
    db.clear_all(drop_file=False)
    db.merge_element_data(snapshot)


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

    legacy_lore_name = chapter_name.replace("chapter_", "lore_record_ch").replace(".md", ".json")
    legacy_lore_path = Path(book_dir) / legacy_lore_name
    if legacy_lore_path.exists():
        return legacy_lore_path.name

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
        "plot_data.json",
    }
    known.update(path.name for path in book_dir.glob("plot_data_*.json"))
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
