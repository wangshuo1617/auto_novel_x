from utils.llm_client import gemini_client,load_prompt_config
import json

class PlotEngineer:
    def __init__(
        self,
        world_setting: dict,
        db_state: dict,
        story_history: dict,
        volume_plan: dict | None = None,
        volume_progress: dict | None = None,
        current_chapter_num: int | None = None,
        review_feedback: str = "",
    ):
        self.world_setting = world_setting
        self.db_state = db_state
        self.story_history = story_history
        self.volume_plan = volume_plan or {}
        self.volume_progress = volume_progress or {}
        self.current_chapter_num = current_chapter_num
        self.review_feedback = review_feedback
        
    def run(self) -> dict:
        system_prompt = load_prompt_config("plot_engineer_prompt", "system")
        
        # 将字典转换为JSON字符串，以便提示词模板正确格式化
        prepare_data = {
            "world_setting": json.dumps(self.world_setting, ensure_ascii=False, indent=2) if isinstance(self.world_setting, dict) else str(self.world_setting),
            "db_state": json.dumps(self.db_state, ensure_ascii=False, indent=2) if isinstance(self.db_state, dict) else str(self.db_state),
            "story_history": json.dumps(self.story_history, ensure_ascii=False, indent=2) if isinstance(self.story_history, dict) else str(self.story_history),
            "volume_plan": json.dumps(self.volume_plan, ensure_ascii=False, indent=2) if isinstance(self.volume_plan, dict) else str(self.volume_plan),
            "volume_progress": json.dumps(self.volume_progress, ensure_ascii=False, indent=2) if isinstance(self.volume_progress, dict) else str(self.volume_progress),
            "current_chapter_num": self.current_chapter_num if self.current_chapter_num is not None else "",
            "review_feedback": self.review_feedback,
        }
        user_prompt = load_prompt_config("plot_engineer_prompt", "user", **prepare_data)
        schema = load_prompt_config("plot_engineer_prompt", "json_schema")
        response = gemini_client(system_prompt, user_prompt, schema)
        return response