"""
阶段1：创世与战略（Initialization & Strategy）
世界观构建、元素设计、第一卷规划。
"""

import json

from agents import ArcDirector, ElementDesigner, WorldArchitect
from utils.structured_response import extract_response_object
from workflows.review_utils import is_review_passed, run_reader_review


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
    review_data = {}
    feedback_text = ""
    for attempt in range(3):
        world_architect = WorldArchitect(loop.trend_analysis, loop.human_idea, review_feedback=feedback_text)
        world_result = world_architect.run()
        review_data = run_reader_review(
            review_stage="world_setting",
            content_to_review=world_result,
            context_payload={
                "trend_analysis": loop.trend_analysis,
                "human_idea": loop.human_idea,
                "main_story_goal": loop.main_story_goal,
            },
            evaluation_focus="检查世界观是否有商业吸引力、核心爽点和后续长线展开空间。",
        )
        if is_review_passed(review_data):
            loop.world_setting = world_result
            break
        feedback_text = "\n".join(review_data.get("improvement_suggestions", []))
        print(f"⚠ 世界观审核未通过（尝试 {attempt + 1}/3）：{review_data.get('review_summary', '无反馈')}")
    else:
        raise RuntimeError(f"世界观审核未通过：{review_data.get('review_summary', '无反馈')}")

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
    review_data = {}
    feedback_text = ""
    element_data = {}
    for attempt in range(3):
        element_designer = ElementDesigner(loop.get_novel_setting())
        element_result = element_designer.run(mode="inital", review_feedback=feedback_text)
        element_data = extract_response_object(element_result, ("element_data",))
        review_data = run_reader_review(
            review_stage="element_design",
            content_to_review=element_data,
            context_payload={
                "world_setting": loop.get_novel_setting(),
                "human_idea": loop.human_idea,
                "main_story_goal": loop.main_story_goal,
            },
            evaluation_focus="检查主角、配角、反派、初始地点和道具是否能支撑开局冲突、爽点兑现和后续剧情扩展。",
        )
        if is_review_passed(review_data):
            break
        feedback_text = "\n".join(review_data.get("improvement_suggestions", []))
        print(f"⚠ 元素设计审核未通过（尝试 {attempt + 1}/3）：{review_data.get('review_summary', '无反馈')}")
    else:
        raise RuntimeError(f"元素设计审核未通过：{review_data.get('review_summary', '无反馈')}")

    element_file = loop.book_dir / "element_data.json"
    with open(element_file, "w", encoding="utf-8") as f:
        json.dump(element_data, f, ensure_ascii=False, indent=2)
    loop.db.merge_element_data(element_data)
    print(f"✓ 初始元素数据已保存: {element_file}")


def _run_arc_director_first_volume(loop) -> None:
    print("\n[F] 分卷导演正在规划第一卷...")
    review_data = {}
    feedback_text = ""
    for attempt in range(3):
        arc_director = ArcDirector(
            world_setting=loop.get_novel_setting(),
            db_state=loop.db.get_state(),
            main_story_goal=loop.main_story_goal,
            previous_volume_summary="",
            volume_num=1,
            review_feedback=feedback_text,
        )
        volume_result = arc_director.run()
        loop.volume_plan = extract_response_object(volume_result, ("output_data",))
        review_data = run_reader_review(
            review_stage="volume_plan",
            content_to_review=loop.volume_plan,
            context_payload={
                "world_setting": loop.get_novel_setting(),
                "db_state": loop.db.get_state(),
                "main_story_goal": loop.main_story_goal,
                "previous_volume_summary": "",
                "volume_num": 1,
            },
            evaluation_focus="检查卷规划是否有明确阶段职责、持续爽点和足够长线推进空间。",
        )
        if is_review_passed(review_data):
            break
        feedback_text = "\n".join(review_data.get("improvement_suggestions", []))
        print(f"⚠ 第一卷规划审核未通过（尝试 {attempt + 1}/3）：{review_data.get('review_summary', '无反馈')}")
    else:
        raise RuntimeError(f"第一卷规划审核未通过：{review_data.get('review_summary', '无反馈')}")

    volume_file = loop.book_dir / f"volume_{loop.current_volume_num}_plan.json"
    with open(volume_file, "w", encoding="utf-8") as f:
        json.dump(loop.volume_plan, f, ensure_ascii=False, indent=2)
    print(f"✓ 第{loop.current_volume_num}卷计划已保存: {volume_file}")
