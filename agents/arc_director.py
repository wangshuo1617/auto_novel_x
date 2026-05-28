import json
from utils.llm_client import gemini_client, load_prompt_config


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
