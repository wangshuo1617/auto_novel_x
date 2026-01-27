import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.llm_client import gemini_client,load_prompt_config
import json
from datetime import datetime

class ContinuityKeeper:
    def __init__(self, db_state: dict, chapter_outline: str, generated_text: str):
        self.db_state = db_state
        self.chapter_outline = chapter_outline
        self.generated_text = generated_text
        self.system_prompt = load_prompt_config("continuity_keeper_prompt", "system")
        prepare_data = {
            "db_state": self.db_state,
            "chapter_outline": self.chapter_outline,
            "generated_text": self.generated_text
        }
        self.user_prompt = load_prompt_config("continuity_keeper_prompt", "user", **prepare_data)
        self.schema = load_prompt_config("continuity_keeper_prompt", "json_schema")
        
    def run(self) -> dict:
        response = gemini_client(self.system_prompt, self.user_prompt, self.schema)
        return response
    
    def save_continuity_data(self, output_data: dict, filepath: str = None) -> str:
        if filepath is None:
            filepath = f"continuity_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(output_data["output_data"])

if __name__ == "__main__":
    with open("draft_data_20260123_172825.md", "r", encoding="utf-8") as f:
        draft_data = f.read()
    db_state = json.load(open("element_data_20260123_164221.json", "r", encoding="utf-8"))
    plot_str = json.load(open("plot_data_20260123_165306.json", "r", encoding="utf-8"))["element_data"]
    plot_data = json.loads(plot_str)
    chapter_outline = plot_data["plot_arc"][0]["plot_points"]
    continuity_keeper = ContinuityKeeper(db_state, chapter_outline, draft_data)
    
    print(continuity_keeper.user_prompt)
    output_data = continuity_keeper.run()
    print(output_data)
    
    continuity_keeper.save_continuity_data(output_data)