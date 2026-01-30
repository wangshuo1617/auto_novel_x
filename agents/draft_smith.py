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
        # 将字典转换为JSON字符串，以便提示词模板正确格式化
        prepare_data = {
            "world_setting": json.dumps(self.world_setting, ensure_ascii=False, indent=2) if isinstance(self.world_setting, dict) else str(self.world_setting),
            "db_state": json.dumps(self.db_state, ensure_ascii=False, indent=2) if isinstance(self.db_state, dict) else str(self.db_state),
            "story_history": self.story_history,
            "cliffhanger": self.cliffhanger,
            "plot_analysis": self.plot_analysis
        }
        
        for key, value in self.plot_data.items():
            # 如果值是字典，转换为JSON字符串
            if isinstance(value, dict):
                prepare_data[key] = json.dumps(value, ensure_ascii=False, indent=2)
            elif isinstance(value, list):
                prepare_data[key] = json.dumps(value, ensure_ascii=False, indent=2)
            else:
                prepare_data[key] = value
        # Normalize plot_points: ensure each beat has a suggested_expansion
        normalized = []
        raw_plot_points = self.plot_data.get("plot_points", [])
        # Target total chapter words; try to hit midpoint of prompt goal
        CHAPTER_TARGET = 3500

        # First pass: collect explicit suggestions and count beats
        explicit_total = 0
        beats_without = []
        for bp in raw_plot_points:
            if isinstance(bp, dict):
                se = bp.get("suggested_expansion")
                if isinstance(se, int) and se > 0:
                    explicit_total += se
                else:
                    beats_without.append(bp)
            else:
                # simple string beat
                beats_without.append(bp)

        # Remaining budget for beats without explicit suggestion
        remaining = max(CHAPTER_TARGET - explicit_total, 600 * max(1, len(raw_plot_points)))
        # Distribute evenly among beats_without, but clamp to reasonable per-beat range
        per_beat = max(600, remaining // max(1, len(beats_without))) if beats_without else 0

        for bp in raw_plot_points:
            if isinstance(bp, dict):
                new_bp = dict(bp)
                if not isinstance(new_bp.get("suggested_expansion"), int):
                    new_bp["suggested_expansion"] = per_beat
                normalized.append(new_bp)
            else:
                # convert simple string to beat object
                normalized.append({
                    "beat": str(bp),
                    "sub_beats": [],
                    "suggested_expansion": per_beat
                })

        prepare_data["plot_points"] = json.dumps(normalized, ensure_ascii=False, indent=2)
        prepare_data["expansion_plan"] = json.dumps({"chapter_target": CHAPTER_TARGET, "beats": [{"beat_index": i+1, "suggested_expansion": b.get("suggested_expansion")} for i,b in enumerate(normalized)]}, ensure_ascii=False, indent=2)
        print("DraftSmith prepare_data plot_points normalized with expansion_plan")
        self.user_prompt = load_prompt_config("draft_smith_prompt", "user", **prepare_data)
        self.schema = load_prompt_config("draft_smith_prompt", "json_schema")
        
    def run(self) -> dict:
        response = gemini_client(self.system_prompt, self.user_prompt, self.schema)
        return response
    
    def save_draft_data(self, draft_data: dict, filepath: str = None) -> str:
        if filepath is None:
            filepath = f"draft_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(draft_data["element_data"])

if __name__ == "__main__":
    with open("world_setting.json", "r", encoding="utf-8") as f:
        world_setting = json.load(f)["novel_setting"]
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