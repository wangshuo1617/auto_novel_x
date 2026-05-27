import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.llm_client import gemini_client,load_prompt_config
import json
from datetime import datetime

class PlotEngineer:
    def __init__(
        self,
        world_setting: dict,
        db_state: dict,
        story_history: dict,
        volume_plan: dict | None = None,
        volume_progress: dict | None = None,
        current_chapter_num: int | None = None,
    ):
        self.world_setting = world_setting
        self.db_state = db_state
        self.story_history = story_history
        self.volume_plan = volume_plan or {}
        self.volume_progress = volume_progress or {}
        self.current_chapter_num = current_chapter_num
        
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
        }
        user_prompt = load_prompt_config("plot_engineer_prompt", "user", **prepare_data)
        schema = load_prompt_config("plot_engineer_prompt", "json_schema")
        response = gemini_client(system_prompt, user_prompt, schema)
        return response
    
    def save_plot_data(self, plot_data: dict, filepath: str = None) -> str:
        if filepath is None:
            filepath = f"plot_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(plot_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    with open("world_setting.json", "r", encoding="utf-8") as f:
        world_setting = json.load(f)["novel_setting"]
    with open("element_data_20260123_164221.json", "r", encoding="utf-8") as f:
        db_state = json.load(f)
    story_history = ""
    plot_engineer = PlotEngineer(world_setting, db_state, story_history)
    plot_data = plot_engineer.run()
    print(plot_data)
    plot_engineer.save_plot_data(plot_data)