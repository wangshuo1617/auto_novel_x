"""
开始新卷：更新卷号、上一卷摘要、分卷导演规划并落盘。
"""

import json

from agents import ArcDirector


def run_new_volume(loop) -> None:
    """开始新的一卷：更新卷号与摘要，调用分卷导演规划新卷并保存。"""
    print("\n" + "=" * 60)
    print(f"开始第 {loop.current_volume_num + 1} 卷")
    print("=" * 60)

    if loop.story_history:
        loop.previous_volume_summary = "\n".join(loop.story_history[-10:])

    loop.current_volume_num += 1
    loop.current_chapter_num = 1

    print("\n[F] 分卷导演正在规划新卷...")
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

    volume_file = loop.book_dir / f"volume_{loop.current_volume_num}_plan.json"
    with open(volume_file, "w", encoding="utf-8") as f:
        json.dump(loop.volume_plan, f, ensure_ascii=False, indent=2)
    print(f"✓ 新卷计划已保存: {volume_file}")
