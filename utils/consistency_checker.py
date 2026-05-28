from __future__ import annotations

from pathlib import Path
from typing import Any

from utils.book_artifacts import (
    list_chapter_files,
    list_lore_files,
    list_plot_files,
    list_volume_plan_files,
    load_json_file,
    parse_chapter_identity,
    parse_lore_identity,
    parse_plot_range_identity,
    parse_volume_plan_number,
)
from utils.database import get_database_for_book
from utils.story_context import story_memory_path


def check_book_consistency(book_dir: str | Path) -> dict[str, Any]:
    root = Path(book_dir)
    issues: list[dict[str, Any]] = []
    chapters = {identity: path for path in list_chapter_files(root) if (identity := parse_chapter_identity(path))}
    lore_records = {identity: path for path in list_lore_files(root) if (identity := parse_lore_identity(path))}
    volume_plans = {parse_volume_plan_number(path): path for path in list_volume_plan_files(root)}
    volume_plans.pop(None, None)

    _check_chapter_lore_pairs(chapters, lore_records, issues)
    _check_volume_plans(chapters, volume_plans, issues)
    _check_story_memory(root, volume_plans, lore_records, issues)
    _check_plot_ranges(root, issues)
    _check_database(root, issues)

    severity_counts = {"error": 0, "warning": 0, "info": 0}
    for issue in issues:
        severity_counts[issue["severity"]] = severity_counts.get(issue["severity"], 0) + 1

    return {
        "status": "error" if severity_counts["error"] else "warning" if severity_counts["warning"] else "ok",
        "summary": {
            "chapters": len(chapters),
            "lore_records": len(lore_records),
            "volume_plans": len(volume_plans),
            "issues": len(issues),
            **severity_counts,
        },
        "issues": issues,
    }


def _issue(issues: list[dict[str, Any]], severity: str, code: str, message: str, detail: Any = None) -> None:
    issues.append({"severity": severity, "code": code, "message": message, "detail": detail})


def _check_chapter_lore_pairs(
    chapters: dict[tuple[int, int], Path],
    lore_records: dict[tuple[int, int], Path],
    issues: list[dict[str, Any]],
) -> None:
    for identity in sorted(chapters.keys() - lore_records.keys()):
        _issue(issues, "error", "missing_lore", f"章节缺少对应 lore：第 {identity[0]} 卷第 {identity[1]} 章")
    for identity in sorted(lore_records.keys() - chapters.keys()):
        _issue(issues, "warning", "orphan_lore", f"lore 没有对应章节：第 {identity[0]} 卷第 {identity[1]} 章")


def _check_volume_plans(
    chapters: dict[tuple[int, int], Path],
    volume_plans: dict[int, Path],
    issues: list[dict[str, Any]],
) -> None:
    chapter_volumes = {volume for volume, _chapter in chapters}
    for volume in sorted(chapter_volumes):
        if volume not in volume_plans:
            _issue(issues, "error", "missing_volume_plan", f"已有第 {volume} 卷章节，但缺少 volume_{volume}_plan.json")
    for volume, path in sorted(volume_plans.items()):
        data = load_json_file(path, {})
        roadmap = data.get("roadmap", []) if isinstance(data, dict) else []
        if not roadmap:
            _issue(issues, "warning", "empty_roadmap", f"第 {volume} 卷计划缺少 roadmap 或 roadmap 为空")


def _check_story_memory(
    root: Path,
    volume_plans: dict[int, Path],
    lore_records: dict[tuple[int, int], Path],
    issues: list[dict[str, Any]],
) -> None:
    path = story_memory_path(root)
    if not path.exists():
        if lore_records:
            _issue(issues, "error", "missing_story_memory", "已有 lore 记录，但缺少 story_memory.json")
        return
    memory = load_json_file(path, {})
    if not isinstance(memory, dict):
        _issue(issues, "error", "invalid_story_memory", "story_memory.json 不是 JSON 对象")
        return
    roadmap_completion = memory.get("roadmap_completion", {})
    if not isinstance(roadmap_completion, dict):
        _issue(issues, "error", "invalid_roadmap_completion", "story_memory.roadmap_completion 不是对象")
        return
    for volume_text, indexes in roadmap_completion.items():
        try:
            volume = int(volume_text)
        except Exception:
            _issue(issues, "warning", "invalid_roadmap_volume_key", f"roadmap_completion 卷号不是整数：{volume_text}")
            continue
        if not isinstance(indexes, list):
            _issue(issues, "error", "invalid_roadmap_indexes", f"第 {volume} 卷 completed_stage_indexes 不是数组")
            continue
        plan = load_json_file(volume_plans.get(volume, ""), {}) if volume in volume_plans else {}
        roadmap = plan.get("roadmap", []) if isinstance(plan, dict) else []
        if not roadmap:
            continue
        invalid = [item for item in indexes if not isinstance(item, int) or item < 1 or item > len(roadmap)]
        if invalid:
            _issue(issues, "warning", "roadmap_completion_out_of_range", f"第 {volume} 卷 roadmap 完成标记越界", invalid)


def _check_plot_ranges(root: Path, issues: list[dict[str, Any]]) -> None:
    seen: dict[tuple[int, int], Path] = {}
    for path in list_plot_files(root):
        identity = parse_plot_range_identity(path)
        if not identity:
            continue
        volume, start, end = identity
        if end < start:
            _issue(issues, "error", "invalid_plot_range", f"剧情大纲范围非法：{path.name}")
        for chapter in range(start, end + 1):
            key = (volume, chapter)
            if key in seen:
                _issue(issues, "warning", "overlapping_plot_range", f"第 {volume} 卷第 {chapter} 章被多个剧情大纲覆盖", [seen[key].name, path.name])
            seen[key] = path


def _check_database(root: Path, issues: list[dict[str, Any]]) -> None:
    db_path = root / "database.db"
    if not db_path.exists():
        _issue(issues, "error", "missing_database", "缺少 database.db")
        return
    db = get_database_for_book(root)
    checks = [
        ("orphan_character_status", "character_status", "character_id", "characters", "id"),
        ("orphan_inventory_character", "character_inventory", "character_id", "characters", "id"),
        ("orphan_inventory_item", "character_inventory", "item_id", "items", "id"),
        ("orphan_relation_character", "character_relations", "character_id", "characters", "id"),
        ("orphan_relation_target", "character_relations", "target_id", "characters", "id"),
        ("orphan_item_placement_item", "item_placement", "item_id", "items", "id"),
        ("orphan_item_placement_location", "item_placement", "location_id", "locations", "id"),
        ("orphan_item_placement_owner", "item_placement", "owner_id", "characters", "id"),
    ]
    for code, table, column, ref_table, ref_column in checks:
        nullable_filter = f" AND {table}.{column} IS NOT NULL" if column in {"location_id", "owner_id"} else ""
        sql = f"""
            SELECT {table}.{column} AS value
            FROM {table}
            LEFT JOIN {ref_table} ON {table}.{column} = {ref_table}.{ref_column}
            WHERE {ref_table}.{ref_column} IS NULL{nullable_filter}
        """
        rows = [row["value"] for row in db.conn.execute(sql).fetchall()]
        if rows:
            _issue(issues, "error", code, f"{table}.{column} 存在无效引用", rows[:20])

    multi_owner_rows = db.conn.execute(
        """
        SELECT item_id, COUNT(DISTINCT character_id) AS owner_count
        FROM character_inventory
        GROUP BY item_id
        HAVING owner_count > 1
        """
    ).fetchall()
    if multi_owner_rows:
        _issue(
            issues,
            "error",
            "multi_owner_item",
            "同一物品出现在多个角色背包中",
            [dict(row) for row in multi_owner_rows],
        )

    placement_mismatches = db.conn.execute(
        """
        SELECT ip.item_id, ip.owner_id, ci.character_id
        FROM item_placement ip
        LEFT JOIN character_inventory ci ON ip.item_id = ci.item_id AND ip.owner_id = ci.character_id
        WHERE ip.owner_id IS NOT NULL AND ci.character_id IS NULL
        """
    ).fetchall()
    if placement_mismatches:
        _issue(
            issues,
            "warning",
            "placement_inventory_mismatch",
            "item_placement 显示物品在角色身上，但背包表缺少对应记录",
            [dict(row) for row in placement_mismatches],
        )
