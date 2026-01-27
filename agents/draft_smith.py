"""正文铸造者模块 - 待实现"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.llm_client import gemini_client,load_prompt_config
import json
from datetime import datetime

class DraftSmith:
    def __init__(self, world_setting: dict, db_state: dict, story_history: str, cliffhanger: str, plot_analysis:str, plot_data: dict):
        self.world_setting = world_setting
        self.db_state = db_state
        self.story_history = story_history
        self.cliffhanger = cliffhanger
        self.plot_analysis = plot_analysis
        self.plot_data = plot_data
        self.system_prompt = load_prompt_config("draft_smith_prompt", "system")
        prepare_data = {
            "world_setting": self.world_setting,
            "db_state": self.db_state,
            "story_history": self.story_history,
            "cliffhanger": self.cliffhanger,
            "plot_analysis": self.plot_analysis
        }
        
        for key, value in self.plot_data.items():
            prepare_data[key] = value
        self.user_prompt = load_prompt_config("draft_smith_prompt", "user", **prepare_data)
        self.schema = load_prompt_config("draft_smith_prompt", "json_schema")
        
    def run(self) -> dict:
        response = gemini_client(self.system_prompt, self.user_prompt, self.schema)
        return response

    # 兼容旧调用：不再直接运行 gemini_client
    def engineer(self) -> dict:
        return self.run()
    
    def save_draft_data(self, draft_data: dict, filepath: str = None) -> str:
        if filepath is None:
            filepath = f"draft_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(draft_data["element_data"])

if __name__ == "__main__":
    with open("world_view_20260123_154339.md", "r", encoding="utf-8") as f:
        world_setting = f.read()
    with open("element_data_20260123_164221.json", "r", encoding="utf-8") as f:
        db_state = json.load(f)
    story_history = ""
    cliffhanger = ""
    plot_str = json.load(open("plot_data_20260123_165306.json", "r", encoding="utf-8"))["element_data"]
    plot_data = json.loads(plot_str)["plot_arc"][0]
    plot_analysis = json.loads(plot_str)["plot_analysis"]
    draft_smith = DraftSmith(world_setting, db_state, story_history, cliffhanger, plot_analysis, plot_data)
    draft_data = draft_smith.run()
    print(draft_data)
    draft_smith.save_draft_data(draft_data)