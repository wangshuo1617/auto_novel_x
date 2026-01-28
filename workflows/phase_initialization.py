"""
阶段1：创世与战略（Initialization & Strategy）
世界观构建、元素设计、第一卷规划。
"""

import json

from agents import ArcDirector, ElementDesigner, WorldArchitect


def run_initialization(loop) -> None:
    """
    阶段1: 创世与战略。
    若 loop 是从已有书籍继续，则跳过；否则执行世界架构师、元素设计师、分卷导演。
    """
    if loop.is_existing_book:
        print("\n从已有书籍继续编写，跳过初始化阶段")
        return

    print("=" * 60)
    print("阶段1: 创世与战略")
    print("=" * 60)

    _run_world_architect(loop)
    _run_element_designer(loop)
    _run_arc_director_first_volume(loop)

    print("\n✓ 阶段1完成！")


def _run_world_architect(loop) -> None:
    print("\n[A] 世界架构师正在构建世界观...")
    world_architect = WorldArchitect(loop.trend_analysis, loop.human_idea)
    world_result = world_architect.run()
    loop.world_setting = world_result

    world_json_file = loop.book_dir / "world_setting.json"
    with open(world_json_file, "w", encoding="utf-8") as f:
        json.dump(loop.world_setting, f, ensure_ascii=False, indent=2)
    print(f"✓ 世界观已保存（JSON格式）: {world_json_file}")

    business = loop.world_setting.get("business_analysis", {})
    md_content = _business_markdown(business)
    world_md_file = loop.book_dir / "world_setting.md"
    with open(world_md_file, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"✓ 商业分析已保存（Markdown格式）: {world_md_file}")


def _business_markdown(business: dict) -> str:
    return f"""# 世界观设定白皮书

## 1. 商业定位分析

* **选定赛道**：{business.get('selected_genre', '')}
* **决策理由**：{business.get('decision_reasoning', '')}
* **拟定书名**：《{business.get('book_title', '')}》
* **一句话简介**：{business.get('logline', '')}

---
*注：完整的小说设定部分请查看 world_setting.json 文件*
"""


def _run_element_designer(loop) -> None:
    print("\n[B] 元素设计师正在创建初始角色和物品...")
    element_designer = ElementDesigner(loop.get_novel_setting())
    element_result = element_designer.run(mode="inital")

    element_data_str = element_result.get("element_data", "{}")
    try:
        element_data = json.loads(element_data_str)
    except Exception:
        element_data = {}

    element_file = loop.book_dir / "element_data.json"
    with open(element_file, "w", encoding="utf-8") as f:
        json.dump(element_data, f, ensure_ascii=False, indent=2)
    loop.db.merge_element_data(element_data)
    print(f"✓ 初始元素数据已保存: {element_file}")


def _run_arc_director_first_volume(loop) -> None:
    print("\n[F] 分卷导演正在规划第一卷...")
    arc_director = ArcDirector(
        world_setting=loop.get_novel_setting(),
        db_state=loop.db.get_state(),
        main_story_goal=loop.main_story_goal,
        previous_volume_summary="",
        volume_num=1,
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
    print(f"✓ 第{loop.current_volume_num}卷计划已保存: {volume_file}")
