"""
AutoNovel-X 主入口
全流程自动化AI网文创作系统
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from agents.trend_scout import TrendScout
from agents.world_architect import WorldArchitect

def main():
    print("开始执行趋势侦察...")
    trend_scout = TrendScout()
    report = trend_scout.scout(platforms=["qidian"], rank_types=["monthly","recommend","new"], max_books=50, analysis_only=True)
    #print(report)
    print("开始执行世界观架构...")
    human_idea = "主角是一座庙，通过吸收香火来获得力量，苟道+非人器物视角+玄幻。"
    world_json = {"trend_analysis": report, "human_idea": human_idea}
    world_architect = WorldArchitect(report, world_json)
    world_view = world_architect.run()
    #print(world_view)
    world_architect.save_world_view(world_view)

if __name__ == "__main__":
    main()