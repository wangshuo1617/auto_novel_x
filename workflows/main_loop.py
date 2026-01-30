"""
自动化小说生成的主循环流程

实现完整的创作流程，包括：
1. 创世与战略（初始化）
2. 策划与编剧（核心循环）
3. 质检与风控（质量检查）
4. 包装与输出（精修）
5. 数据回写与循环（持久化）
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.database import get_database_for_book
from workflows.book_loader import load_existing_book
from workflows.phase_initialization import run_initialization
from workflows.chapter_pipeline import run_chapter_generation
from workflows.phase_new_volume import run_new_volume
from agents.trend_scout import TrendScout

class MainLoop:
    """
    主循环类
    实现完整的自动化小说生成流程，编排各阶段并委托给子模块执行。
    """

    def __init__(
        self,
        output_dir: str = "output",
        book_dir_path: Optional[str] = None,
        trend_analysis: Optional[Dict] = None,
        human_idea: str = "",
        main_story_goal: str = "",
    ):
        """
        初始化主循环

        Args:
            output_dir: 输出目录（新建书籍时使用）
            book_dir_path: 已存在的书籍文件夹路径（若提供则从该文件夹继续编写）
            trend_analysis: 市场趋势分析数据（新建书籍时使用）
            human_idea: 用户创意（新建书籍时使用）
            main_story_goal: 全书目标
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if book_dir_path:
            self.book_dir = Path(book_dir_path)
            if not self.book_dir.exists():
                raise ValueError(f"指定的书籍文件夹不存在: {book_dir_path}")
            if not self.book_dir.is_dir():
                raise ValueError(f"指定的路径不是文件夹: {book_dir_path}")
            self.is_existing_book = True
            print(f"检测到已存在的书籍文件夹: {self.book_dir}")
        else:
            book_id = f"book_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.book_dir = self.output_dir / book_id
            self.book_dir.mkdir(parents=True, exist_ok=True)
            self.is_existing_book = False

        self.trend_analysis = trend_analysis or {}
        self.human_idea = human_idea
        self.main_story_goal = main_story_goal
        self.db = get_database_for_book(self.book_dir)

        self.world_setting: Optional[Dict] = None
        self.volume_plan: Optional[Dict] = None
        self.current_volume_num = 1
        self.current_chapter_num = 1
        self.story_history: List[str] = []
        self.previous_volume_summary = ""
        self.cliffhanger = ""
        self.plot_arc: List[Dict] = []
        self.plot_arc_index: int = 0
        self.lore_records: List[Dict] = []

        if self.is_existing_book:
            load_existing_book(self)

    def get_novel_setting(self) -> Dict:
        """获取小说设定部分（novel_setting），供后续创作流程使用。"""
        try:
            return self.world_setting["novel_setting"]
        except Exception as e:
            raise ValueError("world_setting 缺少 novel_setting（仅支持新JSON世界观格式）") from e

    def initialize(self) -> None:
        """阶段1: 创世与战略。若为已有书籍则跳过。"""
        run_initialization(self)

    def generate_chapter(self) -> Dict[str, Any]:
        """阶段2–4: 生成单章内容。返回本章的 chapter_num / title / content / plot_data。"""
        return run_chapter_generation(self)

    def check_volume_complete(self) -> bool:
        """检查当前卷是否完成。"""
        if self.volume_plan:
            roadmap = self.volume_plan.get("roadmap", [])
            expected_chapters = len(roadmap) * 12
            print(f"当前卷计划包含 {len(roadmap)} 个阶段，预计章节数约为 {expected_chapters} 章")
            return self.current_chapter_num >= expected_chapters
        return self.current_chapter_num >= 50

    def start_new_volume(self) -> None:
        """开始新的一卷：委托给 phase_new_volume 执行。"""
        run_new_volume(self)

    def run(self, max_chapters: int = 100, max_volumes: int = 10) -> None:
        """运行主循环。"""
        print("=" * 60)
        print("自动化小说生成系统启动")
        print("=" * 60)

        self.initialize()

        while self.current_chapter_num <= max_chapters and self.current_volume_num <= max_volumes:
            try:
                self.generate_chapter()

                if self.check_volume_complete():
                    print(f"\n✓ 第 {self.current_volume_num} 卷已完成")
                    if self.current_volume_num < max_volumes:
                        self.start_new_volume()
                    else:
                        print("\n已达到最大卷数，生成结束")
                        break
                else:
                    self.current_chapter_num += 1
            except Exception as e:
                print(f"\n✗ 生成章节时出错: {e}")
                import traceback
                traceback.print_exc()
                break

        print("\n" + "=" * 60)
        print("小说生成完成！")
        print(f"输出目录: {self.book_dir}")
        print("=" * 60)


if __name__ == "__main__":
    # 示例用法1: 新建书籍
    # main_loop = MainLoop(
    #     output_dir="output",
    #     trend_analysis={},
    #     human_idea="主角是一座庙，通过吸收香火来获得力量，苟道+非人器物视角+玄幻。",
    #     main_story_goal="成仙",
    # )
    # main_loop.run(max_chapters=10, max_volumes=1)

    # 示例用法2: 从已有书籍继续编写
    # main_loop = MainLoop(
    #     book_dir_path="output/book_20260127",
    #     main_story_goal="成仙",
    # )
    # main_loop.run(max_chapters=20, max_volumes=2)
    """ scout = TrendScout()
    report = scout.run(
        platforms=["qidian"],
        rank_types=["monthly","recommend","new"],
        max_books=20,
        analysis_only=True
    )

    main_loop = MainLoop(
        output_dir="output",
        trend_analysis=report,
        human_idea="主角是一座庙，通过吸收香火来获得力量，苟道+非人器物视角+玄幻。"
    )
    main_loop.run(max_chapters=10, max_volumes=1) """

    main_loop = MainLoop(
        book_dir_path="output/book_20260130_215334",
    )
    main_loop.run(max_chapters=20, max_volumes=2)