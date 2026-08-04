"""
阶段1：创世与战略（Initialization & Strategy）
世界观构建、元素设计、第一卷规划。
"""

import json

from agents import ArcDirector, ElementDesigner, WorldArchitect
from utils.book_artifacts import infer_main_story_goal_from_world_setting, resolve_book_genre
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
            genre=resolve_book_genre(world_result),
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

    if not str(loop.main_story_goal).strip():
        loop.main_story_goal = infer_main_story_goal_from_world_setting(loop.world_setting)
        if loop.main_story_goal:
            print(f"✓ 已自动生成全书目标：{loop.main_story_goal}")

    business = loop.world_setting.get("business_analysis", {})
    novel_setting = loop.world_setting.get("novel_setting", {})
    md_content = _business_markdown(business, novel_setting)
    world_md_file = loop.book_dir / "world_setting.md"
    with open(world_md_file, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"✓ 商业分析已保存（Markdown格式）: {world_md_file}")


def _business_markdown(business: dict, novel_setting: dict) -> str:
    ending = novel_setting.get("ending_blueprint", {}) if isinstance(novel_setting, dict) else {}
    return f"""# 世界观设定白皮书

## 1. 商业定位分析

* **选定赛道**：{business.get('selected_genre', '')}
* **决策理由**：{business.get('decision_reasoning', '')}
* **拟定书名**：《{business.get('book_title', '')}》
* **全书目标**：{business.get('main_story_goal', '')}
* **短钩子文案**：{business.get('tagline', '')}
* **一句话简介**：{business.get('logline', '')}
* **榜单简介文案**：{business.get('blurb', '')}
* **独特卖点**：{business.get('unique_selling_point', '')}
* **刷榜点击点**：{business.get('click_moment', '')}

## 2. 结构化终局设计

* **女主最终状态**：{ending.get('protagonist_final_state', '')}
* **核心关系结局**：{ending.get('relationship_final_state', '')}
* **世界秩序结局**：{ending.get('world_order_final_state', '')}
* **终极冲突收束**：{ending.get('final_conflict_resolution', '')}
* **终局情绪回报**：{ending.get('emotional_payoff', '')}
* **终章画面钩子**：{ending.get('final_scene_hook', '')}
* **必须回收的伏笔/线索**：{", ".join(ending.get('must_payoff_threads', [])) if isinstance(ending.get('must_payoff_threads', []), list) else ending.get('must_payoff_threads', '')}

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
        element_result = element_designer.run(mode="initial", review_feedback=feedback_text)
        if not isinstance(element_result, dict):
            raise ValueError("ElementDesigner 必须返回 JSON 对象")
        element_data = element_result
        review_data = run_reader_review(
            review_stage="element_design",
            genre=resolve_book_genre(loop.world_setting),
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

    loop.db.merge_element_data(element_data)
    print("✓ 初始元素数据已写入数据库")


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
        if not isinstance(volume_result, dict):
            raise ValueError("ArcDirector 必须返回 JSON 对象")
        loop.volume_plan = volume_result
        review_data = run_reader_review(
            review_stage="volume_plan",
            genre=resolve_book_genre(loop.world_setting),
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
