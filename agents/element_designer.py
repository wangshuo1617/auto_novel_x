import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.llm_client import gemini_client,load_prompt_config
import json
from datetime import datetime

class ElementDesigner:
    def __init__(self, world_setting: dict):
        self.world_setting = world_setting

    def run(self, mode: str = "inital", request_payload: dict = None) -> dict:
        system_prompt = load_prompt_config("element_designer_prompt", "system")
        schema = load_prompt_config("element_designer_prompt", "json_schema")

        if mode == "inital":
            user_prompt = load_prompt_config(
                "element_designer_prompt",
                "inital",
                world_setting=json.dumps(self.world_setting, ensure_ascii=False, indent=2),
            )
        elif mode == "addon":
            user_prompt = load_prompt_config("element_designer_prompt", "addon", request_payload)
        else:
            raise ValueError(f"Unknown mode: {mode}")

        response = gemini_client(system_prompt, user_prompt, schema)
        return response
    
    def save_element_data(self, element_data: dict, filepath: str = None) -> str:
        if filepath is None:
            filepath = f"element_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(element_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    with open("world_setting.json", "r", encoding="utf-8") as f:
        world_setting = json.load(f)["novel_setting"]
    element_designer = ElementDesigner(world_setting)
    element_data = element_designer.run(mode="inital")
    print(element_data)
    element_designer.save_element_data(element_data)