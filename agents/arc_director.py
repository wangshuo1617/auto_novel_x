import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import json
from datetime import datetime
from utils.llm_client import gemini_client, load_prompt_config
from utils.structured_response import extract_response_text


def _to_pretty_json(value) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        return str(value)


class ArcDirector:
    """
    ArcDirector（分卷导演）
    根据世界观、主角当前状态、全书目标与上一卷摘要，规划下一卷（Volume/Arc）的宏观蓝图。
    """

    def __init__(
        self,
        world_setting,
        db_state: dict,
        main_story_goal: str,
        previous_volume_summary: str,
        volume_num: int,
        review_feedback: str = "",
    ):
        self.world_setting = world_setting
        self.db_state = db_state
        self.main_story_goal = main_story_goal
        self.previous_volume_summary = previous_volume_summary
        self.volume_num = volume_num
        self.review_feedback = review_feedback

        self.system_prompt = load_prompt_config("arc_director_prompt", "system")
        prepare_data = {
            "world_setting": _to_pretty_json(self.world_setting),
            "db_state": _to_pretty_json(self.db_state),
            "main_story_goal": self.main_story_goal,
            "previous_volume_summary": self.previous_volume_summary,
            "volume_num": self.volume_num,
            "review_feedback": self.review_feedback,
        }
        self.user_prompt = load_prompt_config("arc_director_prompt", "user", **prepare_data)
        self.schema = load_prompt_config("arc_director_prompt", "json_schema")

    def run(self) -> dict:
        response = gemini_client(self.system_prompt, self.user_prompt, self.schema)
        return response

    def save_volume_plan(self, output_data: dict, filepath: str = None) -> str:
        if filepath is None:
            filepath = f"volume_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(extract_response_text(output_data, ("output_data",)))
        return filepath


if __name__ == "__main__":
    # 简单示例（请根据你的真实数据替换）
    world_setting = "一个玄幻修真世界，香火为力。"
    db_state = {"protagonist": {"name": "无名庙", "level": 1}}
    main_story_goal = "成仙"
    previous_volume_summary = "上一卷主角在山村立足，收拢第一批香火。"
    volume_num = 2

    arc_director = ArcDirector(world_setting, db_state, main_story_goal, previous_volume_summary, volume_num)
    plan = arc_director.run()
    print(plan)
    arc_director.save_volume_plan(plan)
