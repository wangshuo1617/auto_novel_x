"""删除第19章(卷2第1章)产物，回滚story_memory到ch18，重新生成第二卷卷规划后停止。
用新提示词（20-25章/卷 + relationship_arc）重规划第二卷，供人工review。"""
import sys, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.book_artifacts import load_json_file
from workflows.main_loop import MainLoop

BOOK_DIR = Path("output/book_20260628_163239")
TRASH = BOOK_DIR / ".trash_ch19"
TRASH.mkdir(exist_ok=True)

# 1. 备份并删除第19章(卷2)所有产物 + 旧卷2规划 + story_memory
to_remove = [
    "volume_002_chapter_001.md",
    "volume_002_lore_record_ch001.json",
    "volume_002_plot_arc_ch001_ch010.json",
    "volume_2_plan.json",
    "story_memory.json",
]
for name in to_remove:
    p = BOOK_DIR / name
    if p.exists():
        shutil.copy2(p, TRASH / name)
        p.unlink()
        print(f"✓ 删除(已备份): {name}")

# generation_state 里第19章的记录
gs_dir = BOOK_DIR / "generation_state"
for gs in gs_dir.glob("volume_002_*"):
    shutil.copy2(gs, TRASH / gs.name)
    gs.unlink()
    print(f"✓ 删除(已备份): generation_state/{gs.name}")

print("\n--- 重新初始化 loop（将从 lore ch1-18 重建 story_memory）---")
meta = load_json_file(BOOK_DIR / "book_meta.json", {})
goal = str(meta.get("main_story_goal", "")).strip()
ml = MainLoop(book_dir_path=str(BOOK_DIR), main_story_goal=goal)
ml.initialize()

print(f"\n重建后状态: 卷{ml.current_volume_num} 章{ml.current_chapter_num} 全局{ml.current_global_chapter_num}")
print(f"running_summary结尾: ...{ml.story_memory.get('running_summary','')[-80:]}")

# 2. 触发新卷规划（内部会先裁孤儿arc，再跑ArcDirector生成新volume_2_plan）
print("\n--- 生成第二卷规划 ---")
ml.start_new_volume()

print(f"\n✓ 完成。当前: 卷{ml.current_volume_num} 章{ml.current_chapter_num}")
print("第二卷规划已生成，未写正文。请review volume_2_plan.json。")
