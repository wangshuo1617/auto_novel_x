import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.llm_client import gemini_client,load_prompt_config
import json
from datetime import datetime

class StylePolisher:
    def __init__(self, draft_data: dict):
        self.draft_data = draft_data
        self.system_prompt = load_prompt_config("style_polish_prompt", "system")
        self.user_prompt = load_prompt_config("style_polish_prompt", "user", raw_draft = self.draft_data)
        self.schema = load_prompt_config("style_polish_prompt", "json_schema")
        
    def run(self) -> dict:
        response = gemini_client(self.system_prompt, self.user_prompt, self.schema)
        return response
    
    def save_style_data(self, style_data: dict, filepath: str = None) -> str:
        if filepath is None:
            filepath = f"style_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(style_data["element_data"])

if __name__ == "__main__":
    with open("draft_data_20260123_172825.md", "r", encoding="utf-8") as f:
        draft_data = f.read()
    style_polisher = StylePolisher(draft_data)
    style_data = style_polisher.run()
    print(style_data)
    style_polisher.save_style_data(style_data)