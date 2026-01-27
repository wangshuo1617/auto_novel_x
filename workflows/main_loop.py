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
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agents import (
    WorldArchitect,
    ElementDesigner,
    ArcDirector,
    PlotEngineer,
    DraftSmith,
    SimulatedReader,
    ContinuityKeeper,
    LoreArchivist,
    TrendScout,
)
from utils.database import Database


class MainLoop:
    """
    主循环类
    实现完整的自动化小说生成流程
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
            book_dir_path: 已存在的书籍文件夹路径（如果提供，将从该文件夹继续编写）
            trend_analysis: 市场趋势分析数据（新建书籍时使用）
            human_idea: 用户创意（新建书籍时使用）
            main_story_goal: 全书目标
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 判断是新建还是继续已有书籍
        if book_dir_path:
            # 从已存在的文件夹继续
            self.book_dir = Path(book_dir_path)
            if not self.book_dir.exists():
                raise ValueError(f"指定的书籍文件夹不存在: {book_dir_path}")
            if not self.book_dir.is_dir():
                raise ValueError(f"指定的路径不是文件夹: {book_dir_path}")
            self.is_existing_book = True
            print(f"检测到已存在的书籍文件夹: {self.book_dir}")
        else:
            # 创建新书籍目录
            book_id = f"book_{datetime.now().strftime('%Y%m%d')}"
            self.book_dir = self.output_dir / book_id
            self.book_dir.mkdir(parents=True, exist_ok=True)
            self.is_existing_book = False
        
        # 初始化组件
        self.trend_analysis = trend_analysis or {}
        self.human_idea = human_idea
        self.main_story_goal = main_story_goal
        
        # 数据库
        db_path = self.book_dir / "database.db"
        self.db = Database(str(db_path))
        
        # 状态变量
        self.world_setting: Optional[Dict] = None  # 完整的JSON结构，包含business_analysis和novel_setting
        self.volume_plan: Optional[Dict] = None
        self.current_volume_num = 1
        self.current_chapter_num = 1
        self.story_history: List[str] = []
        self.previous_volume_summary = ""
        self.cliffhanger = ""
        
        # 历史档案馆数据
        self.lore_records: List[Dict] = []
        
        # 如果是从已有文件夹开始，加载已有内容
        if self.is_existing_book:
            self._load_existing_book()
    
    def get_novel_setting(self) -> Dict:
        """
        获取小说设定部分（novel_setting），用于传递给后续的创作流程
        """
        try:
            return self.world_setting["novel_setting"]
        except Exception as e:
            raise ValueError("world_setting 缺少 novel_setting（仅支持新JSON世界观格式）") from e

    def _load_existing_book(self):
        """
        从已存在的书籍文件夹加载状态
        确定从哪个章节/卷开始继续编写
        """
        print("=" * 60)
        print("加载已有书籍内容")
        print("=" * 60)
        
        # 1. 加载世界观（仅支持JSON格式）
        world_json_file = self.book_dir / "world_setting.json"
        with open(world_json_file, "r", encoding="utf-8") as f:
            self.world_setting = json.load(f)
        print(f"✓ 已加载世界观（JSON格式）: {world_json_file}")
        
        # 2. 查找所有章节文件，确定当前章节编号
        chapter_files = sorted(self.book_dir.glob("chapter_*.md"))
        if chapter_files:
            # 从文件名中提取章节编号
            max_chapter_num = 0
            for chapter_file in chapter_files:
                try:
                    # 文件名格式: chapter_001.md
                    chapter_num_str = chapter_file.stem.split("_")[1]
                    chapter_num = int(chapter_num_str)
                    max_chapter_num = max(max_chapter_num, chapter_num)
                except (ValueError, IndexError):
                    continue
            
            self.current_chapter_num = max_chapter_num + 1
            print(f"✓ 检测到已有 {max_chapter_num} 章，将从第 {self.current_chapter_num} 章开始")
        else:
            self.current_chapter_num = 1
            print("✓ 未找到已有章节，将从第 1 章开始")
        
        # 3. 查找所有分卷计划文件，确定当前卷编号
        volume_files = sorted(self.book_dir.glob("volume_*_plan.json"))
        if volume_files:
            max_volume_num = 0
            for volume_file in volume_files:
                try:
                    # 文件名格式: volume_1_plan.json
                    volume_num_str = volume_file.stem.split("_")[1]
                    volume_num = int(volume_num_str)
                    max_volume_num = max(max_volume_num, volume_num)
                except (ValueError, IndexError):
                    continue
            
            self.current_volume_num = max_volume_num
            print(f"✓ 检测到已有 {max_volume_num} 卷，当前在第 {self.current_volume_num} 卷")
            
            # 加载当前卷的计划
            volume_file = self.book_dir / f"volume_{self.current_volume_num}_plan.json"
            if volume_file.exists():
                with open(volume_file, "r", encoding="utf-8") as f:
                    self.volume_plan = json.load(f)
                print(f"✓ 已加载当前卷计划: {volume_file}")
        else:
            self.current_volume_num = 1
            print("✓ 未找到已有分卷计划，将从第 1 卷开始")
        
        # 4. 加载历史记录，构建故事历史
        lore_files = sorted(self.book_dir.glob("lore_record_ch*.json"))
        for lore_file in lore_files:
            try:
                with open(lore_file, "r", encoding="utf-8") as f:
                    lore_data_str = f.read()
                    lore_result = {"output_data": lore_data_str}
                    self.lore_records.append(lore_result)
                    
                    # 提取摘要添加到故事历史
                    try:
                        lore_data = json.loads(lore_data_str)
                        summary = lore_data.get("summary_text", "")
                        if summary:
                            self.story_history.append(summary)
                    except Exception:
                        pass
            except Exception as e:
                print(f"⚠ 加载历史记录文件失败 {lore_file}: {e}")
                pass
        
        if self.story_history:
            print(f"✓ 已加载 {len(self.story_history)} 条历史记录")
            # 生成上一卷摘要（用于新卷规划）
            self.previous_volume_summary = "\n".join(self.story_history[-10:])
        
        # 5. 从最后一章提取悬念（如果有）
        if chapter_files:
            try:
                last_chapter_file = chapter_files[-1]
                with open(last_chapter_file, "r", encoding="utf-8") as f:
                    last_chapter_content = f.read()
                    # 尝试提取最后一段作为悬念
                    lines = last_chapter_content.strip().split("\n")
                    if lines:
                        # 取最后几行作为悬念提示
                        self.cliffhanger = "\n".join(lines[-3:])
                        print("✓ 已从上一章提取悬念")
            except Exception:
                pass
        
        # 6. 检查数据库状态
        db_state = self.db.get_state()
        if db_state.get("protagonist"):
            print("✓ 数据库状态已加载")
        else:
            print("⚠ 警告: 数据库中没有主角数据，可能需要重新初始化元素")
        
        print("\n✓ 已有书籍内容加载完成！")
        print(f"  当前卷: {self.current_volume_num}")
        print(f"  当前章: {self.current_chapter_num}")
        print(f"  历史记录: {len(self.story_history)} 条")

    def initialize(self):
        """
        阶段1: 创世与战略 (Initialization & Strategy)
        如果是从已有文件夹开始，则跳过此步骤
        """
        # 如果是从已有文件夹开始，跳过初始化
        if self.is_existing_book:
            print("\n从已有书籍继续编写，跳过初始化阶段")
            return
        
        print("=" * 60)
        print("阶段1: 创世与战略")
        print("=" * 60)
        
        # A. 世界架构师
        print("\n[A] 世界架构师正在构建世界观...")
        world_architect = WorldArchitect(self.trend_analysis, self.human_idea)
        world_result = world_architect.run()
        self.world_setting = world_result  # 直接使用完整的JSON结构
        
        # 保存世界观（JSON格式）
        world_json_file = self.book_dir / "world_setting.json"
        with open(world_json_file, "w", encoding="utf-8") as f:
            json.dump(self.world_setting, f, ensure_ascii=False, indent=2)
        print(f"✓ 世界观已保存（JSON格式）: {world_json_file}")
        
        # 同时保存商业分析部分的Markdown（供人查看）
        business = self.world_setting.get("business_analysis", {})
        md_content = f"""# 世界观设定白皮书

## 1. 商业定位分析

* **选定赛道**：{business.get('selected_genre', '')}
* **决策理由**：{business.get('decision_reasoning', '')}
* **拟定书名**：《{business.get('book_title', '')}》
* **一句话简介**：{business.get('logline', '')}

---
*注：完整的小说设定部分请查看 world_setting.json 文件*
"""
        world_md_file = self.book_dir / "world_setting.md"
        with open(world_md_file, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"✓ 商业分析已保存（Markdown格式）: {world_md_file}")
        
        # B. 元素设计师（初始设计）
        print("\n[B] 元素设计师正在创建初始角色和物品...")
        element_designer = ElementDesigner(self.get_novel_setting())
        element_result = element_designer.run(mode="inital")
        
        # 解析元素数据
        element_data_str = element_result.get("element_data", "{}")
        try:
            element_data = json.loads(element_data_str)
        except Exception:
            element_data = {}
        
        # 保存并合并到数据库
        element_file = self.book_dir / "element_data.json"
        with open(element_file, "w", encoding="utf-8") as f:
            json.dump(element_data, f, ensure_ascii=False, indent=2)
        self.db.merge_element_data(element_data)
        print(f"✓ 初始元素数据已保存: {element_file}")
        
        # F. 分卷导演（规划第一卷）
        print("\n[F] 分卷导演正在规划第一卷...")
        arc_director = ArcDirector(
            world_setting=self.get_novel_setting(),
            db_state=self.db.get_state(),
            main_story_goal=self.main_story_goal,
            previous_volume_summary="",
            volume_num=1,
        )
        volume_result = arc_director.run()
        volume_plan_str = volume_result.get("output_data", "{}")
        try:
            self.volume_plan = json.loads(volume_plan_str)
        except Exception:
            self.volume_plan = {}
        
        # 保存分卷计划
        volume_file = self.book_dir / f"volume_{self.current_volume_num}_plan.json"
        with open(volume_file, "w", encoding="utf-8") as f:
            json.dump(self.volume_plan, f, ensure_ascii=False, indent=2)
        print(f"✓ 第一卷计划已保存: {volume_file}")
        
        print("\n✓ 阶段1完成！")

    def generate_chapter(self) -> Dict[str, Any]:
        """
        阶段2-4: 生成单章内容
        
        Returns:
            生成的章节数据
        """
        print("\n" + "=" * 60)
        print(f"生成第 {self.current_chapter_num} 章")
        print("=" * 60)
        
        # =======================
        # 阶段2: 策划与编剧
        # =======================
        print("\n[阶段2] 策划与编剧")
        
        # C. 情景工程师
        print("\n[C] 情景工程师正在规划剧情...")
        
        # 准备历史档案馆的相关设定
        lore_context = ""
        if self.lore_records:
            recent_records = self.lore_records[-5:]  # 最近5条记录
            lore_context = "相关历史设定：\n"
            for record in recent_records:
                try:
                    record_data = json.loads(record.get("output_data", "{}"))
                    summary = record_data.get("summary_text", "")
                    if summary:
                        lore_context += f"- {summary}\n"
                except Exception:
                    pass
        
        # 构建故事历史（合并所有上下文信息）
        story_history_text = "\n".join(self.story_history[-3:]) if self.story_history else "这是小说的开始。"
        
        # 合并所有历史信息
        full_story_history = f"{story_history_text}\n\n{lore_context}"
        
        # 保存full_story_history供后续使用
        story_history_for_draft = story_history_text
        
        plot_engineer = PlotEngineer(
            world_setting=self.get_novel_setting(),
            db_state=self.db.get_state(),
            story_history=full_story_history,
        )
        plot_result = plot_engineer.run()
        plot_data_str = plot_result.get("element_data", "{}")
        
        try:
            plot_data = json.loads(plot_data_str)
        except Exception:
            plot_data = {}
        
        plot_arc = plot_data.get("plot_arc", [])
        if not plot_arc:
            raise ValueError("情景工程师未生成有效的剧情大纲")
        
        # 使用第一个章节的大纲
        chapter_outline = plot_arc[0]
        plot_analysis = plot_data.get("plot_analysis", "")
        
        print(f"✓ 剧情大纲已生成: {chapter_outline.get('title', '未命名')}")
        
        # E. 正文塑造者（跳过Marketing标题党）
        print("\n[E] 正文塑造者正在创作正文...")
        
        # 准备参与角色数据（转换为JSON字符串）
        participating_char_ids = chapter_outline.get("participating_characters", [])
        participating_char_data = []
        db_state = self.db.get_state()
        
        # 查找主角
        if db_state.get("protagonist"):
            participating_char_data.append(db_state["protagonist"])
        
        # 查找其他角色
        for char_id in participating_char_ids:
            for char_list in [db_state.get("supporting_characters", []), db_state.get("villains", [])]:
                for char in char_list:
                    if char.get("id") == char_id:
                        participating_char_data.append(char)
                        break
        
        # 将角色数据转换为JSON字符串
        participating_characters_json = json.dumps(participating_char_data, ensure_ascii=False, indent=2)
        
        # 准备plot_data，包含所有需要的字段
        plot_data_for_draft = {
            "location_id": chapter_outline.get("location_id", ""),
            "plot_points": json.dumps(chapter_outline.get("plot_points", []), ensure_ascii=False),
            "participating_characters": participating_characters_json,
            "key_items_used": json.dumps(chapter_outline.get("key_items_used", []), ensure_ascii=False),
            "chapter_num": chapter_outline.get("chapter_num", self.current_chapter_num),
            "expected_reader_reaction": chapter_outline.get("expected_reader_reaction", ""),
            "emotional_tone": chapter_outline.get("emotional_tone", ""),
            "cliffhanger": chapter_outline.get("cliffhanger", ""),
        }
        
        draft_smith = DraftSmith(
            world_setting=self.get_novel_setting(),
            db_state=self.db.get_state(),
            story_history=story_history_for_draft,
            cliffhanger=self.cliffhanger,
            plot_analysis=plot_analysis,
            plot_data=plot_data_for_draft,
        )
        draft_result = draft_smith.run()
        
        # 解析返回结果
        raw_text = draft_result.get("draft_content", "")
        chapter_title = draft_result.get("title", f"第{self.current_chapter_num}章")
        
        # 如果没有draft_content，尝试从element_data中解析
        if not raw_text:
            try:
                draft_data_str = draft_result.get("element_data", "")
                if draft_data_str:
                    draft_data = json.loads(draft_data_str)
                    raw_text = draft_data.get("draft_content", "")
                    chapter_title = draft_data.get("title", chapter_title)
            except Exception:
                pass
        print(f"✓ 正文初稿已生成: {chapter_title}")
        
        # =======================
        # 阶段3: 质检与风控
        # =======================
        print("\n[阶段3] 质检与风控")
        
        max_retries = 3
        retry_count = 0
        audit_passed = False
        
        while retry_count < max_retries and not audit_passed:
            # I. 毒舌书评人
            print(f"\n[I] 毒舌书评人正在审核... (尝试 {retry_count + 1}/{max_retries})")
            genre = "玄幻/系统流"  # 可以从世界观中提取
            simulated_reader = SimulatedReader(genre=genre, content_to_review=raw_text)
            review_result = simulated_reader.run()
            review_data_str = review_result.get("output_data", "{}")
            
            try:
                review_data = json.loads(review_data_str)
            except Exception:
                review_data = {"decision": "PASS", "score": 3}
            
            decision = review_data.get("decision", "PASS")
            score = review_data.get("score", 3)
            
            if decision == "REWRITE" or score < 3:
                print(f"✗ 审核未通过 (评分: {score}/5)")
                print(f"  反馈: {review_data.get('review_summary', '无')}")
                
                # 如果爽度不合格，重写大纲
                if retry_count < max_retries - 1:
                    print("  → 重新规划剧情大纲...")
                    # 使用反馈意见重新生成
                    feedback_text = "\n".join(review_data.get("improvement_suggestions", []))
                    full_story_history_with_feedback = f"{full_story_history}\n\n反馈意见：\n{feedback_text}"
                    plot_engineer = PlotEngineer(
                        world_setting=self.get_novel_setting(),
                        db_state=self.db.get_state(),
                        story_history=full_story_history_with_feedback,
                    )
                    plot_result = plot_engineer.run()
                    plot_data_str = plot_result.get("element_data", "{}")
                    try:
                        plot_data = json.loads(plot_data_str)
                        plot_arc = plot_data.get("plot_arc", [])
                        if plot_arc:
                            chapter_outline = plot_arc[0]
                            plot_analysis = plot_data.get("plot_analysis", "")
                            
                            # 重新准备参与角色数据
                            participating_char_ids = chapter_outline.get("participating_characters", [])
                            participating_char_data = []
                            db_state = self.db.get_state()
                            
                            if db_state.get("protagonist"):
                                participating_char_data.append(db_state["protagonist"])
                            
                            for char_id in participating_char_ids:
                                for char_list in [db_state.get("supporting_characters", []), db_state.get("villains", [])]:
                                    for char in char_list:
                                        if char.get("id") == char_id:
                                            participating_char_data.append(char)
                                            break
                            
                            participating_characters_json = json.dumps(participating_char_data, ensure_ascii=False, indent=2)
                            
                            # 重新构建plot_data_for_draft
                            plot_data_for_draft = {
                                "location_id": chapter_outline.get("location_id", ""),
                                "plot_points": json.dumps(chapter_outline.get("plot_points", []), ensure_ascii=False),
                                "participating_characters": participating_characters_json,
                                "key_items_used": json.dumps(chapter_outline.get("key_items_used", []), ensure_ascii=False),
                                "chapter_num": chapter_outline.get("chapter_num", self.current_chapter_num),
                                "expected_reader_reaction": chapter_outline.get("expected_reader_reaction", ""),
                                "emotional_tone": chapter_outline.get("emotional_tone", ""),
                                "cliffhanger": chapter_outline.get("cliffhanger", ""),
                            }
                    except Exception:
                        pass
                    
                    # 重新生成正文
                    draft_smith = DraftSmith(
                        world_setting=self.get_novel_setting(),
                        db_state=self.db.get_state(),
                        story_history=story_history_for_draft,
                        cliffhanger=self.cliffhanger,
                        plot_analysis=plot_analysis,
                        plot_data=plot_data_for_draft,
                    )
                    draft_result = draft_smith.run()
                    raw_text = draft_result.get("draft_content", "")
                    chapter_title = draft_result.get("title", f"第{self.current_chapter_num}章")
                    if not raw_text:
                        try:
                            draft_data_str = draft_result.get("element_data", "")
                            if draft_data_str:
                                draft_data = json.loads(draft_data_str)
                                raw_text = draft_data.get("draft_content", "")
                                chapter_title = draft_data.get("title", chapter_title)
                        except Exception:
                            pass
                retry_count += 1
                continue
            
            print(f"✓ 爽度审核通过 (评分: {score}/5)")
            
            # J. 连贯性守门员
            print("\n[J] 连贯性守门员正在检查逻辑...")
            chapter_outline_str = json.dumps(chapter_outline, ensure_ascii=False)
            
            continuity_keeper = ContinuityKeeper(
                db_state=self.db.get_state(),
                chapter_outline=chapter_outline_str,
                generated_text=raw_text,
            )
            continuity_result = continuity_keeper.run()
            continuity_data_str = continuity_result.get("output_data", "{}")
            
            try:
                continuity_data = json.loads(continuity_data_str)
            except Exception:
                continuity_data = {"audit_result": "PASS"}
            
            audit_result = continuity_data.get("audit_result", "PASS")
            
            if audit_result == "FAIL":
                print("✗ 逻辑检查未通过")
                print(f"  错误: {continuity_data.get('review_comments', '无')}")
                
                # 如果逻辑不合格，重写正文
                if retry_count < max_retries - 1:
                    print("  → 重新生成正文...")
                    draft_smith = DraftSmith(
                        world_setting=self.get_novel_setting(),
                        db_state=self.db.get_state(),
                        story_history=story_history_for_draft,
                        cliffhanger=self.cliffhanger,
                        plot_analysis=plot_analysis,
                        plot_data=plot_data_for_draft,
                    )
                    draft_result = draft_smith.run()
                    raw_text = draft_result.get("draft_content", "")
                    chapter_title = draft_result.get("title", f"第{self.current_chapter_num}章")
                    if not raw_text:
                        try:
                            draft_data_str = draft_result.get("element_data", "")
                            if draft_data_str:
                                draft_data = json.loads(draft_data_str)
                                raw_text = draft_data.get("draft_content", "")
                                chapter_title = draft_data.get("title", chapter_title)
                        except Exception:
                            pass
                retry_count += 1
                continue
            
            print("✓ 逻辑检查通过")
            audit_passed = True
            
            # 提取数据更新
            database_updates = continuity_data.get("database_updates", {})
            if database_updates:
                print("  → 更新数据库状态...")
                self.db.update(database_updates)
        
        if not audit_passed:
            raise RuntimeError(f"章节生成失败，已重试 {max_retries} 次")
        
        # =======================
        # 阶段4: 数据回写
        # =======================
        print("\n[阶段4] 数据回写")
        
        # G. 历史档案馆
        print("\n[G] 历史档案馆正在归档...")
        lore_archivist = LoreArchivist(
            chapter_num=self.current_chapter_num,
            chapter_title=chapter_title,
            final_chapter_text=raw_text,
        )
        lore_result = lore_archivist.run()
        self.lore_records.append(lore_result)
        
        # 保存历史记录
        lore_file = self.book_dir / f"lore_record_ch{self.current_chapter_num}.json"
        with open(lore_file, "w", encoding="utf-8") as f:
            f.write(lore_result.get("output_data", "{}"))
        print(f"✓ 历史记录已保存: {lore_file}")
        
        # 更新故事历史
        try:
            lore_data = json.loads(lore_result.get("output_data", "{}"))
            summary = lore_data.get("summary_text", "")
            if summary:
                self.story_history.append(summary)
        except Exception:
            pass
        
        # 更新悬念（用于下一章）
        try:
            lore_data = json.loads(lore_result.get("output_data", "{}"))
            plot_threads = lore_data.get("plot_threads", {})
            opened_threads = plot_threads.get("opened", [])
            if opened_threads:
                # 使用最新的悬念作为下一章的钩子
                self.cliffhanger = opened_threads[-1].get("description", "")
        except Exception:
            self.cliffhanger = chapter_outline.get("cliffhanger", "")
                
        # 保存章节
        chapter_file = self.book_dir / f"chapter_{self.current_chapter_num:03d}.md"
        with open(chapter_file, "w", encoding="utf-8") as f:
            f.write(f"# {chapter_title}\n\n")
            f.write(raw_text)
        print(f"✓ 章节已保存: {chapter_file}")
        
        return {
            "chapter_num": self.current_chapter_num,
            "title": chapter_title,
            "content": raw_text,
            "plot_data": plot_data,
        }

    def check_volume_complete(self) -> bool:
        """
        检查当前卷是否完成
        
        Returns:
            是否完成
        """
        # 简单判断：如果当前章节数达到一定数量（如50章），则认为本卷完成
        # 或者可以根据volume_plan中的roadmap来判断
        if self.volume_plan:
            roadmap = self.volume_plan.get("roadmap", [])
            # 假设每个阶段约10-15章
            expected_chapters = len(roadmap) * 12
            return self.current_chapter_num >= expected_chapters
        return self.current_chapter_num >= 50  # 默认50章一卷

    def start_new_volume(self):
        """开始新的一卷"""
        print("\n" + "=" * 60)
        print(f"开始第 {self.current_volume_num + 1} 卷")
        print("=" * 60)
        
        # 生成上一卷摘要
        if self.story_history:
            self.previous_volume_summary = "\n".join(self.story_history[-10:])
        
        self.current_volume_num += 1
        self.current_chapter_num = 1
        
        # F. 分卷导演（规划新卷）
        print("\n[F] 分卷导演正在规划新卷...")
        arc_director = ArcDirector(
            world_setting=self.get_novel_setting(),
            db_state=self.db.get_state(),
            main_story_goal=self.main_story_goal,
            previous_volume_summary=self.previous_volume_summary,
            volume_num=self.current_volume_num,
        )
        volume_result = arc_director.run()
        volume_plan_str = volume_result.get("output_data", "{}")
        try:
            self.volume_plan = json.loads(volume_plan_str)
        except Exception:
            self.volume_plan = {}
        
        # 保存分卷计划
        volume_file = self.book_dir / f"volume_{self.current_volume_num}_plan.json"
        with open(volume_file, "w", encoding="utf-8") as f:
            json.dump(self.volume_plan, f, ensure_ascii=False, indent=2)
        print(f"✓ 新卷计划已保存: {volume_file}")
        
        # 可能需要扩展元素（新地图、新角色等）
        if self.volume_plan:
            # 这里可以根据volume_plan的需求调用ElementDesigner的addon模式
            pass

    def run(self, max_chapters: int = 100, max_volumes: int = 10):
        """
        运行主循环
        
        Args:
            max_chapters: 最大章节数
            max_volumes: 最大卷数
        """
        print("=" * 60)
        print("自动化小说生成系统启动")
        print("=" * 60)
        
        # 阶段1: 初始化
        self.initialize()
        
        # 核心循环
        while self.current_chapter_num <= max_chapters and self.current_volume_num <= max_volumes:
            try:
                # 生成章节
                chapter_data = self.generate_chapter()
                
                # 检查本卷是否完成
                if self.check_volume_complete():
                    print(f"\n✓ 第 {self.current_volume_num} 卷已完成")
                    if self.current_volume_num < max_volumes:
                        self.start_new_volume()
                    else:
                        print("\n已达到最大卷数，生成结束")
                        break
                else:
                    # 继续下一章
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
    #     trend_analysis={},  # 需要提供趋势分析数据
    #     human_idea="主角是一座庙，通过吸收香火来获得力量，苟道+非人器物视角+玄幻。",
    #     main_story_goal="成仙",
    # )
    # main_loop.run(max_chapters=10, max_volumes=1)
    
    # 示例用法2: 从已有书籍继续编写
    # main_loop = MainLoop(
    #     book_dir_path="output/book_20260127",  # 指定已存在的书籍文件夹路径
    #     main_story_goal="成仙",  # 可以更新全书目标
    # )
    # main_loop.run(max_chapters=20, max_volumes=2)
    
    trend_analysis = TrendScout()
    trend=trend_analysis.run(
        platforms=["qidian"],
        rank_types=["monthly","recommend","new"],
        max_books=20,
        analysis_only=True
    )
    
    main_loop = MainLoop(
        output_dir="output",
        trend_analysis=trend,
        human_idea="主角是一座庙，通过吸收香火来获得力量，苟道+非人器物视角+玄幻。"
    )
    main_loop.run(max_chapters=10, max_volumes=1)
