import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.llm_client import gemini_client,load_prompt_config
import json
from datetime import datetime

class WorldArchitect:
    def __init__(self, trend_analysis: dict, human_idea: str):
        self.trend_analysis = trend_analysis
        self.human_idea = human_idea
        
    def run(self) -> dict:
        system_prompt = load_prompt_config("world_architect_prompt", "system")
        world_json = {"trend_analysis": self.trend_analysis, "human_idea": self.human_idea}
        user_prompt = load_prompt_config("world_architect_prompt", "user", **world_json)
        schema = load_prompt_config("world_architect_prompt", "json_schema")
        response = gemini_client(system_prompt, user_prompt, schema)
        return response

    # 兼容旧调用：不再直接运行 gemini_client
    def architect(self) -> dict:
        return self.run()
    
    def save_world_view(self, world_view: dict, filepath: str = None) -> str:
        if filepath is None:
            filepath = f"world_view_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(world_view["world_view"])
            
if __name__ == "__main__":
    trend_analysis = json.load(open("trend_report_20260123_145749.json", "r", encoding="utf-8"))
    human_idea = "主角是一座庙，通过吸收香火来获得力量，苟道+非人器物视角+玄幻。"
    architect = WorldArchitect(trend_analysis, human_idea)
    world_view = architect.run()
    print(world_view)
    architect.save_world_view(world_view)