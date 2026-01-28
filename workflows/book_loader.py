"""
从已存在的书籍目录加载世界观、章节、历史、分卷与剧情弧等状态。
"""

import json
from pathlib import Path

from agents import ArcDirector, PlotEngineer


def load_existing_book(loop) -> None:
    """
    从已存在的书籍文件夹加载状态，确定从哪个章节/卷开始继续编写。
    会直接修改 loop 上的 world_setting / story_history / lore_records / volume_plan /
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

    # 2. 查找所有章节文件，确定当前章节编号
    chapter_files = sorted(book_dir.glob("chapter_*.md"))
    if chapter_files:
        max_chapter_num = _max_chapter_from_files(chapter_files)
        loop.current_chapter_num = max_chapter_num + 1
        print(f"✓ 检测到已有 {max_chapter_num} 章，将从第 {loop.current_chapter_num} 章开始")
    else:
        loop.current_chapter_num = 1
        print("✓ 未找到已有章节，将从第 1 章开始")

    # 3. 加载历史记录，构建故事历史
    _load_lore_and_story_history(loop, book_dir)

    # 4. 恢复或生成 plot_arc
    _load_or_build_plot_arc(loop, book_dir)

    # 5. 确定当前卷与卷计划
    _load_volume_plan(loop, book_dir)

    # 再次确保上一卷摘要（用于新卷规划）
    if loop.story_history:
        loop.previous_volume_summary = "\n".join(loop.story_history[-10:])

    # 6. 从最后一章提取悬念
    if chapter_files:
        _load_cliffhanger_from_last_chapter(loop, chapter_files)

    # 7. 检查数据库状态
    db_state = db.get_state()
    if db_state.get("protagonist"):
        print("✓ 数据库状态已加载")
    else:
        print("⚠ 警告: 数据库中没有主角数据，可能需要重新初始化元素")

    print("\n✓ 已有书籍内容加载完成！")
    print(f"  当前卷: {loop.current_volume_num}")
    print(f"  当前章: {loop.current_chapter_num}")
    print(f"  历史记录: {len(loop.story_history)} 条")


def _max_chapter_from_files(chapter_files) -> int:
    max_chapter_num = 0
    for chapter_file in chapter_files:
        try:
            chapter_num_str = chapter_file.stem.split("_")[1]
            chapter_num = int(chapter_num_str)
            max_chapter_num = max(max_chapter_num, chapter_num)
        except (ValueError, IndexError):
            continue
    return max_chapter_num


def _load_lore_and_story_history(loop, book_dir: Path) -> None:
    lore_files = sorted(book_dir.glob("lore_record_ch*.json"))
    for lore_file in lore_files:
        try:
            with open(lore_file, "r", encoding="utf-8") as f:
                lore_data_str = f.read()
                loop.lore_records.append({"output_data": lore_data_str})
                try:
                    lore_data = json.loads(lore_data_str)
                    summary = lore_data.get("summary_text", "")
                    if summary:
                        loop.story_history.append(summary)
                except Exception:
                    pass
        except Exception as e:
            print(f"⚠ 加载历史记录文件失败 {lore_file}: {e}")

    if loop.story_history:
        print(f"✓ 已加载 {len(loop.story_history)} 条历史记录")
        loop.previous_volume_summary = "\n".join(loop.story_history[-10:])


def _load_or_build_plot_arc(loop, book_dir: Path) -> None:
    plot_file = book_dir / "plot_data.json"
    if plot_file.exists():
        try:
            with open(plot_file, "r", encoding="utf-8") as f:
                plot_data = json.load(f)
            if isinstance(plot_data, dict):
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
                print(f"✓ 已恢复 plot_arc（{len(loop.plot_arc)} 条），下一条索引: {loop.plot_arc_index}")
        except Exception as e:
            print(f"⚠ 无法读取/解析 plot_data.json: {e}")
        return

    print("✓ 未找到 plot_data.json，尝试使用剧情工程师生成 plot_arc...")
    try:
        plot_engineer = PlotEngineer(
            world_setting=loop.get_novel_setting(),
            db_state=loop.db.get_state(),
            story_history="\n".join(loop.story_history) if loop.story_history else "",
        )
        plot_result = plot_engineer.run()
        plot_data_str = plot_result.get("element_data") or plot_result.get("output_data") or "{}"
        try:
            plot_data = json.loads(plot_data_str) if isinstance(plot_data_str, str) else (plot_data_str or {})
        except Exception:
            plot_data = {}

        loop.plot_arc = plot_data.get("plot_arc", []) or []
        loop.plot_arc_index = 0
        if loop.plot_arc:
            try:
                with open(plot_file, "w", encoding="utf-8") as f:
                    json.dump(plot_data, f, ensure_ascii=False, indent=2)
                print(f"✓ 已生成并保存 plot_data.json（{len(loop.plot_arc)} 条）: {plot_file}")
            except Exception:
                print("⚠ 已生成 plot_arc，但无法保存 plot_data.json 到磁盘")
        else:
            print("⚠ 剧情工程师未返回有效的 plot_arc，继续但 plot_arc 为空")
    except Exception as e:
        print(f"⚠ 运行剧情工程师失败: {e}")
        loop.plot_arc = []
        loop.plot_arc_index = 0


def _load_volume_plan(loop, book_dir: Path) -> None:
    volume_files = sorted(book_dir.glob("volume_*_plan.json"))
    if volume_files:
        max_volume_num = 0
        for volume_file in volume_files:
            try:
                volume_num_str = volume_file.stem.split("_")[1]
                volume_num = int(volume_num_str)
                max_volume_num = max(max_volume_num, volume_num)
            except (ValueError, IndexError):
                continue

        loop.current_volume_num = max_volume_num
        print(f"✓ 检测到已有 {max_volume_num} 卷，当前在第 {loop.current_volume_num} 卷")

        volume_file = book_dir / f"volume_{loop.current_volume_num}_plan.json"
        if volume_file.exists():
            with open(volume_file, "r", encoding="utf-8") as f:
                loop.volume_plan = json.load(f)
            print(f"✓ 已加载当前卷计划: {volume_file}")
        return

    loop.current_volume_num = 1
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
        volume_plan_str = volume_result.get("output_data", "{}")
        try:
            loop.volume_plan = json.loads(volume_plan_str)
        except Exception:
            loop.volume_plan = {}

        volume_file = book_dir / f"volume_{loop.current_volume_num}_plan.json"
        with open(volume_file, "w", encoding="utf-8") as f:
            json.dump(loop.volume_plan, f, ensure_ascii=False, indent=2)
        print(f"✓ 已生成并保存默认分卷计划: {volume_file}")
    except Exception as e:
        print(f"⚠ 无法生成默认分卷计划: {e}")
        loop.volume_plan = {}
        print("✓ 将从第 1 卷开始（未生成分卷计划）")


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
