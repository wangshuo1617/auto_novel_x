import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.llm_client import gemini_client,load_prompt_config
import json
from datetime import datetime

class WorldArchitect:
    def __init__(self, trend_analysis: dict, human_idea: str, review_feedback: str = ""):
        self.trend_analysis = trend_analysis
        self.human_idea = human_idea
        self.review_feedback = review_feedback
        
    def run(self) -> dict:
        system_prompt = load_prompt_config("world_architect_prompt", "system")
        world_json = {
            "trend_analysis": self.trend_analysis,
            "human_idea": self.human_idea,
            "review_feedback": self.review_feedback,
        }
        user_prompt = load_prompt_config("world_architect_prompt", "user", **world_json)
        schema = load_prompt_config("world_architect_prompt", "json_schema")
        response = gemini_client(system_prompt, user_prompt, schema)
        return response
    
    def save_world_view(self, world_view: dict, filepath: str = None) -> str:
        """保存世界观，同时保存JSON格式和Markdown格式（商业分析部分）"""
        if filepath is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            json_filepath = f"world_view_{timestamp}.json"
            md_filepath = f"world_view_{timestamp}.md"
        else:
            json_filepath = filepath.replace('.md', '.json') if filepath.endswith('.md') else filepath + '.json'
            md_filepath = filepath.replace('.json', '.md') if filepath.endswith('.json') else filepath + '.md'
        
        # 保存完整JSON格式
        with open(json_filepath, "w", encoding="utf-8") as f:
            json.dump(world_view, f, ensure_ascii=False, indent=2)
        
        # 保存Markdown格式（仅商业分析部分，供人查看）
        business = world_view.get("business_analysis", {})
        md_content = f"""# 世界观设定白皮书

## 1. 商业定位分析

* **选定赛道**：{business.get('selected_genre', '')}
* **决策理由**：{business.get('decision_reasoning', '')}
* **拟定书名**：《{business.get('book_title', '')}》
* **一句话简介**：{business.get('logline', '')}

---
*注：完整的小说设定部分请查看对应的JSON文件*
"""
        with open(md_filepath, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        return json_filepath
            
if __name__ == "__main__":
    trend_analysis = json.load(open("trend_report_20260123_145749.json", "r", encoding="utf-8"))
    human_idea = "主角是一座庙，通过吸收香火来获得力量，苟道+非人器物视角+玄幻。"
    architect = WorldArchitect(trend_analysis, human_idea)
    world_view = architect.run()
    print(world_view)
    architect.save_world_view(world_view)