"""
AutoNovel-X 主入口
全流程自动化AI网文创作系统
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def main():
    """主函数"""
    print("AutoNovel-X: 全流程自动化AI网文创作系统")
    print("=" * 50)
    print("\n可用模块:")
    print("  - TrendScout: 市场情报与题材自动化")
    print("  - WorldArchitect: 世界观架构")
    print("  - PlotEngineer: 情节工程")
    print("  - DraftSmith: 正文生成")
    print("  - ContinuityKeeper: 连贯性管理")
    print("  - StylePolisher: 风格润色")
    print("\n使用示例:")
    print("  from agents.trend_scout import TrendScout")
    print("  scout = TrendScout()")
    print("  report = scout.scout(platforms=['qidian'])")
    print("=" * 50)


if __name__ == "__main__":
    main()
