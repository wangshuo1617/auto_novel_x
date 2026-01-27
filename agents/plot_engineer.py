import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.llm_client import gemini_client,load_prompt_config
import json
from datetime import datetime

class PlotEngineer:
    def __init__(self, world_setting: dict, db_state: dict, story_history: dict):
        self.world_setting = world_setting
        self.db_state = db_state
        self.story_history = story_history
        
    def run(self) -> dict:
        system_prompt = load_prompt_config("plot_engineer_prompt", "system")
        
        prepare_data = {
            "world_setting": self.world_setting,
            "db_state": self.db_state,
            "story_history": self.story_history
        }
        user_prompt = load_prompt_config("plot_engineer_prompt", "user", **prepare_data)
        schema = load_prompt_config("plot_engineer_prompt", "json_schema")
        response = gemini_client(system_prompt, user_prompt, schema)
        return response

    # 兼容旧调用：不再直接运行 gemini_client
    def engineer(self) -> dict:
        return self.run()
    
    def save_plot_data(self, plot_data: dict, filepath: str = None) -> str:
        if filepath is None:
            filepath = f"plot_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(plot_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    with open("world_view_20260123_154339.md", "r", encoding="utf-8") as f:
        world_setting = f.read()
    with open("element_data_20260123_164221.json", "r", encoding="utf-8") as f:
        db_state = json.load(f)
    story_history = ""
    plot_engineer = PlotEngineer(world_setting, db_state, story_history)
    plot_data = plot_engineer.run()
    print(plot_data)
    plot_engineer.save_plot_data(plot_data)