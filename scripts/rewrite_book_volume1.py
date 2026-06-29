"""
一次性脚本：保留已有 world_setting.json，用指定 prompt 预设重做
元素设计 + 第一卷规划，并生成第一卷正文。

用途：给《穿肠毒药》这类"总纲好但卷规划/正文节奏拖沓"的书重写。
前置：已手动清空下游产物（章节/lore/plot_arc/卷计划/story_memory/db），
      仅保留 world_setting.json / .md / book_meta.json。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.book_artifacts import load_json_file
from utils.llm_logging import use_llm_log_context
from utils.prompt_presets import use_prompt_preset
from utils.story_context import empty_story_memory
from workflows.main_loop import MainLoop
from workflows.phase_initialization import _run_arc_director_first_volume, _run_element_designer

BOOK_DIR = "output/book_20260607_092053"
PRESET = "女频网文提示词模板"
MAX_CHAPTERS = 26   # 第一卷约20章，留缓冲
MAX_VOLUMES = 1     # 只跑第一卷


def _purge_generated(book_dir: Path) -> None:
    """删除 __init__ 自动加载阶段可能用旧预设/空库生成的临时产物。"""
    patterns = [
        "volume_*_chapter_*.md",
        "volume_*_lore_record_*.json",
        "volume_*_plot_arc_*.json",
        "volume_*_plan.json",
    ]
    for pat in patterns:
        for p in book_dir.glob(pat):
            p.unlink()
    for name in ("story_memory.json", "latest_generation_state.json"):
        fp = book_dir / name
        if fp.exists():
            fp.unlink()


def main() -> None:
    meta = load_json_file(Path(BOOK_DIR) / "book_meta.json", {})
    main_story_goal = str(meta.get("main_story_goal", "")).strip()

    print("=" * 60)
    print(f"重写第一卷：{BOOK_DIR}")
    print(f"预设：{PRESET}")
    print(f"全书目标：{main_story_goal}")
    print("=" * 60, flush=True)

    # __init__ 会触发 load_existing_book（加载 world_setting，可能生成临时卷计划/plot_arc）
    ml = MainLoop(book_dir_path=BOOK_DIR, main_story_goal=main_story_goal, prompt_preset_id=PRESET)

    with use_prompt_preset(PRESET), use_llm_log_context(ml.book_dir, "rewrite_v1_init"):
        print("\n[B] 用新预设重建元素数据库...", flush=True)
        _run_element_designer(ml)
        print("\n[F] 用新预设重做第一卷规划...", flush=True)
        _run_arc_director_first_volume(ml)

    # 清掉自动加载阶段写盘的临时产物（element/arc 已在内存与 db / volume_1_plan.json 落定）
    # 注意：_run_arc_director_first_volume 已重写 volume_1_plan.json，需保留它
    book_dir = ml.book_dir
    for p in book_dir.glob("volume_*_plot_arc_*.json"):
        p.unlink()
    for name in ("story_memory.json", "latest_generation_state.json"):
        fp = book_dir / name
        if fp.exists():
            fp.unlink()

    # 重置到第1章干净起点
    ml.current_volume_num = 1
    ml.current_chapter_num = 1
    ml.current_global_chapter_num = 1
    ml.plot_arc = []
    ml.plot_arc_index = 0
    ml.lore_records = []
    ml.story_memory = empty_story_memory()
    ml.cliffhanger = ""
    ml.previous_volume_summary = ""

    print("\n[G] 开始生成第一卷正文...", flush=True)
    # run() 会再次调用 initialize()（existing book 会跳过），然后进入章节循环
    ml.is_existing_book = True
    ml.run(max_chapters=MAX_CHAPTERS, max_volumes=MAX_VOLUMES)

    print("\n=== 第一卷重写完成 ===", flush=True)
    chapters = sorted(book_dir.glob("volume_001_chapter_*.md"))
    print(f"生成章节数：{len(chapters)}", flush=True)


if __name__ == "__main__":
    main()
