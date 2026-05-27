from __future__ import annotations

import contextlib
import contextvars
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from utils.book_artifacts import ensure_directory, load_json_file, write_json_file


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPT_PRESETS_DIR = PROJECT_ROOT / "prompt_presets"
DEFAULT_PROMPT_PRESET_ID = "default"
PRESET_META_FILE = "preset_meta.json"

_ACTIVE_PROMPT_PRESET_ID: contextvars.ContextVar[str] = contextvars.ContextVar(
    "active_prompt_preset_id",
    default=DEFAULT_PROMPT_PRESET_ID,
)


def list_prompt_template_names() -> list[str]:
    preset_dir = _preset_dir(DEFAULT_PROMPT_PRESET_ID)
    if not preset_dir.exists():
        return []
    return sorted(path.stem for path in preset_dir.glob("*_prompt.json"))


def _default_prompt_config(template_name: str) -> dict[str, Any]:
    template_path = _template_file_path(DEFAULT_PROMPT_PRESET_ID, template_name)
    config = load_json_file(template_path, {})
    if not isinstance(config, dict) or not config:
        raise ValueError(f"默认 Prompt 缺少模板配置: {template_name}")
    return config


def ensure_default_prompt_preset() -> None:
    preset_dir = _preset_dir(DEFAULT_PROMPT_PRESET_ID)
    ensure_directory(preset_dir)

    meta_path = preset_dir / PRESET_META_FILE
    if not meta_path.exists():
        write_json_file(
            meta_path,
            {
                "id": DEFAULT_PROMPT_PRESET_ID,
                "name": "默认 Prompt",
                "description": "系统默认 Prompt 来源。",
                "source_preset_id": "",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            },
        )

    if not list_prompt_template_names():
        raise ValueError("默认 Prompt 预设目录为空，请先提供 prompt_presets/default 下的模板文件")


def list_prompt_presets() -> list[dict[str, Any]]:
    ensure_default_prompt_preset()
    preset_entries: list[dict[str, Any]] = []
    for preset_dir in PROMPT_PRESETS_DIR.iterdir():
        if not preset_dir.is_dir():
            continue
        meta = _load_preset_meta(preset_dir.name)
        meta["template_count"] = len(list(_iter_template_paths(preset_dir.name)))
        preset_entries.append(meta)

    def sort_key(entry: dict[str, Any]) -> tuple[int, str, str]:
        if entry.get("id") == DEFAULT_PROMPT_PRESET_ID:
            return (0, "", "")
        return (
            1,
            str(entry.get("updated_at", "")),
            str(entry.get("name", "")),
        )

    return sorted(preset_entries, key=sort_key, reverse=False)


def get_prompt_preset_view(preset_id: str) -> dict[str, Any]:
    ensure_default_prompt_preset()
    normalized_id = normalize_prompt_preset_id(preset_id)
    preset_dir = _preset_dir(normalized_id)
    if not preset_dir.exists():
        raise ValueError(f"Prompt 预设不存在: {preset_id}")

    templates: dict[str, dict[str, Any]] = {}
    for template_name in list_prompt_template_names():
        templates[template_name] = load_prompt_template(template_name, normalized_id)

    return {
        "meta": _load_preset_meta(normalized_id),
        "templates": templates,
    }


def create_prompt_preset(name: str, description: str = "", source_preset_id: str = DEFAULT_PROMPT_PRESET_ID) -> dict[str, Any]:
    ensure_default_prompt_preset()
    display_name = name.strip()
    if not display_name:
        raise ValueError("Prompt 预设名称不能为空")

    preset_id = normalize_prompt_preset_id(display_name)
    if preset_id == DEFAULT_PROMPT_PRESET_ID:
        raise ValueError("不能覆盖默认 Prompt 预设")

    preset_dir = _preset_dir(preset_id)
    if preset_dir.exists():
        raise ValueError(f"Prompt 预设已存在: {preset_id}")

    source_view = get_prompt_preset_view(source_preset_id)
    ensure_directory(preset_dir)

    now = datetime.now().isoformat()
    write_json_file(
        preset_dir / PRESET_META_FILE,
        {
            "id": preset_id,
            "name": display_name,
            "description": description.strip(),
            "source_preset_id": normalize_prompt_preset_id(source_preset_id),
            "created_at": now,
            "updated_at": now,
        },
    )

    for template_name, config in source_view["templates"].items():
        write_json_file(_template_file_path(preset_id, template_name), config)

    return get_prompt_preset_view(preset_id)


def save_prompt_template(preset_id: str, template_name: str, updates: dict[str, Any]) -> dict[str, Any]:
    ensure_default_prompt_preset()
    normalized_id = normalize_prompt_preset_id(preset_id)
    if not updates:
        raise ValueError("没有可保存的 Prompt 内容")

    base_config = load_prompt_template(template_name, normalized_id)
    allowed_keys = set(base_config.keys())
    unknown_keys = set(updates.keys()) - allowed_keys
    if unknown_keys:
        raise ValueError(f"存在未知 Prompt 字段: {', '.join(sorted(unknown_keys))}")

    base_config.update(updates)
    write_json_file(_template_file_path(normalized_id, template_name), base_config)
    _touch_preset_meta(normalized_id)
    return base_config


def save_prompt_preset_meta(preset_id: str, *, name: str | None = None, description: str | None = None) -> dict[str, Any]:
    ensure_default_prompt_preset()
    normalized_id = normalize_prompt_preset_id(preset_id)
    meta = _load_preset_meta(normalized_id)
    if normalized_id == DEFAULT_PROMPT_PRESET_ID and name and name.strip() != meta.get("name"):
        raise ValueError("默认 Prompt 预设不支持改名")

    if name is not None and name.strip():
        meta["name"] = name.strip()
    if description is not None:
        meta["description"] = description.strip()
    meta["updated_at"] = datetime.now().isoformat()
    write_json_file(_preset_dir(normalized_id) / PRESET_META_FILE, meta)
    return meta


def load_prompt_template(template_name: str, preset_id: str | None = None) -> dict[str, Any]:
    ensure_default_prompt_preset()
    default_config = _default_prompt_config(template_name)
    normalized_id = normalize_prompt_preset_id(preset_id or get_active_prompt_preset_id())
    if normalized_id == DEFAULT_PROMPT_PRESET_ID:
        return default_config

    template_path = _template_file_path(normalized_id, template_name)
    if not template_path.exists():
        return default_config

    saved = load_json_file(template_path, {})
    if not isinstance(saved, dict):
        return default_config

    merged = dict(default_config)
    merged.update(saved)
    return merged


def get_active_prompt_preset_id() -> str:
    ensure_default_prompt_preset()
    return _ACTIVE_PROMPT_PRESET_ID.get()


@contextlib.contextmanager
def use_prompt_preset(preset_id: str | None):
    ensure_default_prompt_preset()
    normalized_id = normalize_prompt_preset_id(preset_id or DEFAULT_PROMPT_PRESET_ID)
    token = _ACTIVE_PROMPT_PRESET_ID.set(normalized_id)
    try:
        yield normalized_id
    finally:
        _ACTIVE_PROMPT_PRESET_ID.reset(token)


def normalize_prompt_preset_id(value: str) -> str:
    raw = (value or DEFAULT_PROMPT_PRESET_ID).strip().lower().replace("_", "-")
    raw = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", raw, flags=re.UNICODE)
    raw = re.sub(r"-{2,}", "-", raw)
    normalized = raw.strip("-")
    return normalized or DEFAULT_PROMPT_PRESET_ID


def _preset_dir(preset_id: str) -> Path:
    return PROMPT_PRESETS_DIR / normalize_prompt_preset_id(preset_id)


def _template_file_path(preset_id: str, template_name: str) -> Path:
    return _preset_dir(preset_id) / f"{template_name}.json"


def _iter_template_paths(preset_id: str):
    preset_dir = _preset_dir(preset_id)
    if not preset_dir.exists():
        return []
    return sorted(path for path in preset_dir.glob("*_prompt.json"))


def _load_preset_meta(preset_id: str) -> dict[str, Any]:
    normalized_id = normalize_prompt_preset_id(preset_id)
    meta = load_json_file(_preset_dir(normalized_id) / PRESET_META_FILE, {})
    if not isinstance(meta, dict):
        meta = {}

    return {
        "id": normalized_id,
        "name": meta.get("name") or ("默认 Prompt" if normalized_id == DEFAULT_PROMPT_PRESET_ID else normalized_id),
        "description": meta.get("description", ""),
        "source_preset_id": meta.get("source_preset_id", ""),
        "created_at": meta.get("created_at", ""),
        "updated_at": meta.get("updated_at", ""),
    }


def _touch_preset_meta(preset_id: str) -> None:
    meta = _load_preset_meta(preset_id)
    meta["updated_at"] = datetime.now().isoformat()
    write_json_file(_preset_dir(preset_id) / PRESET_META_FILE, meta)
