"""从已有书籍续写：标准 MainLoop 续写路径，跑完第一卷。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.book_artifacts import load_json_file
from workflows.main_loop import MainLoop

BOOK_DIR = "output/book_20260607_092053"
MAX_CHAPTERS = 24
MAX_VOLUMES = 1

meta = load_json_file(Path(BOOK_DIR) / "book_meta.json", {})
goal = str(meta.get("main_story_goal", "")).strip()

print("=" * 60, flush=True)
print(f"续写第一卷：{BOOK_DIR}", flush=True)
print("=" * 60, flush=True)

ml = MainLoop(book_dir_path=BOOK_DIR, main_story_goal=goal)
ml.run(max_chapters=MAX_CHAPTERS, max_volumes=MAX_VOLUMES)

chapters = sorted(Path(BOOK_DIR).glob("volume_001_chapter_*.md"))
print(f"\n=== 完成，当前章节数：{len(chapters)} ===", flush=True)
