"""用最新番茄女频预设 + 假千金脑洞，跑初始化（世界观+元素+第一卷规划）。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workflows.main_loop import MainLoop

HUMAN_IDEA = (
    "古言，明朝衍生世界观。假千金被赶出侯府后不争家产，自己出府经商挣钱，"
    "为求平安向手握实权的权臣交保护费，而这位权臣的公开身份竟是宫里的假太监（男主）。"
    "女主用经商和现代商业头脑，与逐渐收紧、压迫女性的'女子教条'制度作斗争。"
    "最终男女主联手扶持新皇上位，推翻旧教条，创办女学。"
)
MAIN_GOAL = (
    "假千金从被弃出府的商女，成长为撼动女子教条的女商魁首，"
    "与假太监权臣联手扶持新皇、创办女学，改写女性命运。"
)

print("=" * 60, flush=True)
print("番茄女频预设 · 假千金脑洞 · 初始化", flush=True)
print("=" * 60, flush=True)

ml = MainLoop(
    output_dir="output",
    human_idea=HUMAN_IDEA,
    main_story_goal=MAIN_GOAL,
    prompt_preset_id="番茄女频提示词模板",
)
print(f"BOOK_DIR={ml.book_dir}", flush=True)
ml.initialize()
print(f"BOOK_DIR_FINAL={ml.book_dir}", flush=True)
print("=== 初始化完成 ===", flush=True)
