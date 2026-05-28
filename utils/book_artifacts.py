from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


CHAPTER_FILE_RE = re.compile(r"^volume_(?P<volume>\d{3})_chapter_(?P<chapter>\d{3})\.md$")
LORE_FILE_RE = re.compile(r"^volume_(?P<volume>\d{3})_lore_record_ch(?P<chapter>\d{3})\.json$")
VOLUME_PLAN_FILE_RE = re.compile(r"^volume_(?P<volume>\d+)_plan\.json$")
PLOT_RANGE_FILE_RE = re.compile(r"^volume_(?P<volume>\d{3})_plot_arc_ch(?P<start>\d{3})_ch(?P<end>\d{3})\.json$")


def ensure_directory(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def load_json_file(path: str | Path, default: Any = None) -> Any:
    file_path = Path(path)
    if not file_path.exists():
        return {} if default is None else default
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json_file(path: str | Path, data: Any) -> Path:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return file_path


def write_text_file(path: str | Path, content: str) -> Path:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return file_path


def resolve_relative_path(root_dir: str | Path, relative_path: str) -> Path:
    root = Path(root_dir).resolve()
    candidate = (root / relative_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"非法路径: {relative_path}")
    return candidate


def chapter_artifact_path(book_dir: str | Path, volume_num: int, chapter_num: int) -> Path:
    return Path(book_dir) / f"volume_{volume_num:03d}_chapter_{chapter_num:03d}.md"


def lore_artifact_path(book_dir: str | Path, volume_num: int, chapter_num: int) -> Path:
    return Path(book_dir) / f"volume_{volume_num:03d}_lore_record_ch{chapter_num:03d}.json"


def plot_arc_artifact_path(book_dir: str | Path, volume_num: int, start_chapter_num: int, end_chapter_num: int) -> Path:
    return Path(book_dir) / f"volume_{volume_num:03d}_plot_arc_ch{start_chapter_num:03d}_ch{end_chapter_num:03d}.json"


def parse_chapter_identity(path: str | Path) -> tuple[int, int] | None:
    name = Path(path).name
    match = CHAPTER_FILE_RE.match(name)
    if match:
        return int(match.group("volume")), int(match.group("chapter"))

    return None


def parse_lore_identity(path: str | Path) -> tuple[int, int] | None:
    name = Path(path).name
    match = LORE_FILE_RE.match(name)
    if match:
        return int(match.group("volume")), int(match.group("chapter"))

    return None


def parse_volume_plan_number(path: str | Path) -> int | None:
    match = VOLUME_PLAN_FILE_RE.match(Path(path).name)
    if not match:
        return None
    return int(match.group("volume"))


def parse_plot_range_identity(path: str | Path) -> tuple[int, int, int] | None:
    match = PLOT_RANGE_FILE_RE.match(Path(path).name)
    if not match:
        return None
    return int(match.group("volume")), int(match.group("start")), int(match.group("end"))


def list_book_dirs(output_dir: str | Path) -> list[Path]:
    directory = ensure_directory(output_dir)
    return sorted(
        [path for path in directory.iterdir() if path.is_dir() and path.name.startswith("book_")],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def list_chapter_files(book_dir: str | Path) -> list[Path]:
    directory = Path(book_dir)
    chapter_files = [path for path in directory.glob("*.md") if parse_chapter_identity(path)]
    return sorted(chapter_files, key=lambda path: parse_chapter_identity(path) or (0, 0))


def list_lore_files(book_dir: str | Path) -> list[Path]:
    directory = Path(book_dir)
    lore_files = [path for path in directory.glob("*.json") if parse_lore_identity(path)]
    return sorted(lore_files, key=lambda path: parse_lore_identity(path) or (0, 0))


def list_volume_plan_files(book_dir: str | Path) -> list[Path]:
    directory = Path(book_dir)
    volume_files = [path for path in directory.glob("volume_*_plan.json") if parse_volume_plan_number(path) is not None]
    return sorted(volume_files, key=lambda path: parse_volume_plan_number(path) or 0)


def list_plot_files(book_dir: str | Path) -> list[Path]:
    directory = Path(book_dir)
    range_files = [path for path in directory.glob("volume_*_plot_arc_ch*_ch*.json") if parse_plot_range_identity(path)]
    return sorted(range_files, key=lambda path: parse_plot_range_identity(path) or (0, 0, 0))


def list_artifact_paths(book_dir: str | Path) -> list[str]:
    directory = Path(book_dir)
    files = [path for path in directory.iterdir() if path.is_file() and not path.name.startswith(".")]
    return sorted(path.name for path in files)


def detect_book_title(book_dir: str | Path) -> str:
    world_setting = load_json_file(Path(book_dir) / "world_setting.json", {})
    business = world_setting.get("business_analysis", {}) if isinstance(world_setting, dict) else {}
    title = business.get("book_title", "")
    return title or Path(book_dir).name


def chapter_display_name(path: str | Path) -> str:
    identity = parse_chapter_identity(path)
    if not identity:
        return Path(path).name
    volume_num, chapter_num = identity
    return f"第{volume_num}卷 · 第{chapter_num}章"
