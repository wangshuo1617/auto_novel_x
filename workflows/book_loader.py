"""
从已存在的书籍目录加载世界观、章节、历史、分卷与剧情弧等状态。
"""

import json
from pathlib import Path

from agents import ArcDirector, PlotEngineer
from utils.book_artifacts import (
    list_chapter_files,
    list_lore_files,
    list_plot_files,
    list_volume_plan_files,
    parse_plot_range_identity,
    plot_arc_artifact_path,
    parse_lore_identity,
    parse_chapter_identity,
    parse_volume_plan_number,
    write_json_file,
)
from utils.story_context import build_volume_progress, merge_lore_into_story_memory, normalize_story_memory, story_context_for_plot, story_memory_path


def load_existing_book(loop) -> None:
    """
    从已存在的书籍文件夹加载状态，确定从哪个章节/卷开始继续编写。
    会直接修改 loop 上的 world_setting / lore_records / volume_plan /
    plot_arc / plot_arc_index / current_chapter_num / current_volume_num / cliffhanger 等属性。
    """
    print("=" * 60)
    print("加载已有书籍内容")
    print("=" * 60)

    book_dir = loop.book_dir
    db = loop.db

    # 1. 加载世界观（仅支持 JSON 格式）
    world_json_file = book_dir / "world_setting.json"
    with open(world_json_file, "r", encoding="utf-8") as f:
        loop.world_setting = json.load(f)
    print(f"✓ 已加载世界观（JSON格式）: {world_json_file}")

    # 2. 查找章节/分卷文件，恢复当前卷与当前章节编号
    chapter_files = list_chapter_files(book_dir)
    loop.current_global_chapter_num = len(chapter_files) + 1
    _load_volume_plan(loop, book_dir, chapter_files)
    _set_current_chapter_num(loop, chapter_files)

    # 3. 加载 lore 与 story_memory
    _load_lore_and_story_memory(loop, book_dir)

    # 4. 恢复或生成 plot_arc
    _load_or_build_plot_arc(loop, book_dir)

    # 5. 再次确保上一卷摘要（用于新卷规划）
    if loop.story_memory.get("running_summary"):
        loop.previous_volume_summary = loop.story_memory["running_summary"]

    # 6. 从最后一章提取悬念
    if chapter_files and not loop.story_memory.get("last_cliffhanger"):
        _load_cliffhanger_from_last_chapter(loop, chapter_files)
    elif loop.story_memory.get("last_cliffhanger"):
        loop.cliffhanger = loop.story_memory["last_cliffhanger"]

    # 7. 检查数据库状态
    db_state = db.get_state()
    if db_state.get("protagonist"):
        print("✓ 数据库状态已加载")
    else:
        print("⚠ 警告: 数据库中没有主角数据，可能需要重新初始化元素")

    print("\n✓ 已有书籍内容加载完成！")
    print(f"  当前卷: {loop.current_volume_num}")
    print(f"  当前章: {loop.current_chapter_num}")
    print(f"  全局下一章: {loop.current_global_chapter_num}")
    print(f"  lore 记录: {len(loop.lore_records)} 条")


def _set_current_chapter_num(loop, chapter_files) -> None:
    if not chapter_files:
        loop.current_chapter_num = 1
        print("✓ 未找到已有章节，将从第 1 章开始")
        return

    current_volume_chapters = []
    for chapter_file in chapter_files:
        identity = parse_chapter_identity(chapter_file)
        if not identity:
            continue
        volume_num, chapter_num = identity
        if volume_num == loop.current_volume_num:
            current_volume_chapters.append(chapter_num)

    if current_volume_chapters:
        max_chapter_num = max(current_volume_chapters)
        loop.current_chapter_num = max_chapter_num + 1
        print(
            f"✓ 检测到第 {loop.current_volume_num} 卷已有 {max_chapter_num} 章，"
            f"将从第 {loop.current_chapter_num} 章开始"
        )
        return

    loop.current_chapter_num = 1
    print(f"✓ 第 {loop.current_volume_num} 卷尚无章节，将从第 1 章开始")


def _load_lore_and_story_memory(loop, book_dir: Path) -> None:
    lore_files = list_lore_files(book_dir)
    memory_file = story_memory_path(book_dir)
    if memory_file.exists():
        try:
            with open(memory_file, "r", encoding="utf-8") as f:
                loop.story_memory = normalize_story_memory(json.load(f))
            print(f"✓ 已加载 story_memory: {memory_file}")
        except Exception as e:
            print(f"⚠ 加载 story_memory 失败 {memory_file}: {e}")
    for lore_file in lore_files:
        try:
            with open(lore_file, "r", encoding="utf-8") as f:
                lore_data_str = f.read()
                lore_data = json.loads(lore_data_str)
                loop.lore_records.append(lore_data)
                try:
                    if not memory_file.exists():
                        lore_identity = parse_lore_identity(lore_file)
                        volume_num = lore_identity[0] if lore_identity else None
                        chapter_num = len(loop.lore_records)
                        loop.story_memory = merge_lore_into_story_memory(
                            loop.story_memory,
                            lore_data,
                            chapter_num=chapter_num,
                            chapter_title=f"第{chapter_num}章",
                            volume_num=volume_num,
                        )
                except Exception:
                    pass
        except Exception as e:
            print(f"⚠ 加载历史记录文件失败 {lore_file}: {e}")

    if loop.lore_records:
        print(f"✓ 已加载 {len(loop.lore_records)} 条 lore 记录")
    if not memory_file.exists() and loop.story_memory:
        try:
            write_json_file(memory_file, loop.story_memory)
            print(f"✓ 已根据 lore 重建 story_memory: {memory_file}")
        except Exception as e:
            print(f"⚠ 写入重建后的 story_memory 失败 {memory_file}: {e}")


def _load_or_build_plot_arc(loop, book_dir: Path) -> None:
    plot_file = _select_plot_file_for_current_position(
        book_dir,
        loop.current_volume_num,
        loop.current_chapter_num,
    )

    if plot_file is not None and plot_file.exists():
        try:
            with open(plot_file, "r", encoding="utf-8") as f:
                plot_data = json.load(f)
            if isinstance(plot_data, dict):
                _ensure_plot_arc_range_file(loop, plot_data)
                loop.plot_arc = plot_data.get("plot_arc", []) or []
                idx = 0
                for entry in loop.plot_arc:
                    try:
                        ent_num = entry.get("chapter_num")
                        if isinstance(ent_num, int) and ent_num < loop.current_chapter_num:
                            idx += 1
                    except Exception:
                        continue
                loop.plot_arc_index = idx
                print(f"✓ 已从 {plot_file.name} 恢复 plot_arc（{len(loop.plot_arc)} 条），下一条索引: {loop.plot_arc_index}")
        except Exception as e:
            print(f"⚠ 无法读取/解析 {plot_file.name}: {e}")
        return

    print("✓ 未找到匹配当前卷章的 plot_arc 缓存，尝试使用剧情工程师生成 plot_arc...")
    try:
        volume_progress = build_volume_progress(loop.volume_plan or {}, loop.current_chapter_num)
        plot_engineer = PlotEngineer(
            world_setting=loop.get_novel_setting(),
            db_state=loop.db.get_state(),
            story_history=story_context_for_plot(loop.story_memory),
            volume_plan=loop.volume_plan or {},
            volume_progress=volume_progress,
            current_chapter_num=loop.current_chapter_num,
        )
        plot_result = plot_engineer.run()
        if not isinstance(plot_result, dict):
            raise ValueError("PlotEngineer 必须返回 JSON 对象")
        plot_data = plot_result
        plot_data["volume_progress"] = volume_progress
        plot_data["volume_num"] = loop.current_volume_num

        loop.plot_arc = plot_data.get("plot_arc", []) or []
        loop.plot_arc_index = 0
        if loop.plot_arc:
            try:
                range_file = _ensure_plot_arc_range_file(loop, plot_data)
                print(f"✓ 已生成并保存 {range_file.name}（{len(loop.plot_arc)} 条）")
            except Exception:
                print("⚠ 已生成 plot_arc，但无法保存剧情大纲到磁盘")
        else:
            print("⚠ 剧情工程师未返回有效的 plot_arc，继续但 plot_arc 为空")
    except Exception as e:
        print(f"⚠ 运行剧情工程师失败: {e}")
        loop.plot_arc = []
        loop.plot_arc_index = 0


def _select_plot_file_for_current_position(book_dir: Path, volume_num: int, chapter_num: int) -> Path | None:
    for plot_file in list_plot_files(book_dir):
        identity = parse_plot_range_identity(plot_file)
        if not identity:
            continue
        file_volume, start_chapter, end_chapter = identity
        if file_volume == volume_num and start_chapter <= chapter_num <= end_chapter:
            return plot_file

    return None


def _load_volume_plan(loop, book_dir: Path, chapter_files) -> None:
    volume_files = list_volume_plan_files(book_dir)
    chapter_volumes = [
        volume_num
        for chapter_file in chapter_files
        if (identity := parse_chapter_identity(chapter_file))
        for volume_num, _chapter_num in [identity]
    ]
    latest_volume_from_chapters = max(chapter_volumes, default=0)

    if volume_files:
        max_volume_num = max(parse_volume_plan_number(volume_file) or 0 for volume_file in volume_files)
        max_volume_num = max(max_volume_num, latest_volume_from_chapters or 0)

        loop.current_volume_num = max_volume_num
        print(f"✓ 检测到已有 {max_volume_num} 卷，当前在第 {loop.current_volume_num} 卷")

        volume_file = book_dir / f"volume_{loop.current_volume_num}_plan.json"
        if volume_file.exists():
            with open(volume_file, "r", encoding="utf-8") as f:
                loop.volume_plan = json.load(f)
            print(f"✓ 已加载当前卷计划: {volume_file}")
        return

    loop.current_volume_num = latest_volume_from_chapters or 1
    if latest_volume_from_chapters:
        print(f"✓ 未找到分卷计划文件，按章节文件恢复到第 {loop.current_volume_num} 卷")
        loop.volume_plan = {}
        return

    print("✓ 未找到已有分卷计划，尝试生成默认分卷计划...")
    try:
        arc_director = ArcDirector(
            world_setting=loop.get_novel_setting(),
            db_state=loop.db.get_state(),
            main_story_goal=loop.main_story_goal,
            previous_volume_summary=loop.previous_volume_summary,
            volume_num=loop.current_volume_num,
        )
        volume_result = arc_director.run()
        if not isinstance(volume_result, dict):
            raise ValueError("ArcDirector 必须返回 JSON 对象")
        loop.volume_plan = volume_result

        volume_file = book_dir / f"volume_{loop.current_volume_num}_plan.json"
        with open(volume_file, "w", encoding="utf-8") as f:
            json.dump(loop.volume_plan, f, ensure_ascii=False, indent=2)
        print(f"✓ 已生成并保存默认分卷计划: {volume_file}")
    except Exception as e:
        print(f"⚠ 无法生成默认分卷计划: {e}")
        loop.volume_plan = {}
        print("✓ 将从第 1 卷开始（未生成分卷计划）")


def _ensure_plot_arc_range_file(loop, plot_data: dict) -> Path:
    plot_data.setdefault("volume_num", loop.current_volume_num)
    plot_arc = plot_data.get("plot_arc", [])
    chapter_nums = [
        entry.get("chapter_num")
        for entry in plot_arc
        if isinstance(entry, dict) and isinstance(entry.get("chapter_num"), int)
    ]
    if not chapter_nums:
        raise ValueError("plot_arc 缺少有效章节号")

    range_file = plot_arc_artifact_path(loop.book_dir, loop.current_volume_num, min(chapter_nums), max(chapter_nums))
    if range_file.exists():
        return range_file
    write_json_file(range_file, plot_data)
    return range_file


def _load_cliffhanger_from_last_chapter(loop, chapter_files) -> None:
    try:
        last_chapter_file = chapter_files[-1]
        with open(last_chapter_file, "r", encoding="utf-8") as f:
            last_chapter_content = f.read()
            lines = last_chapter_content.strip().split("\n")
            if lines:
                loop.cliffhanger = "\n".join(lines[-3:])
                print("✓ 已从上一章提取悬念")
    except Exception:
        pass
