"""
阶段2–4：单章生成流水线
策划与编剧 → 质检与风控 → 数据回写。
"""

import json
from typing import Any, Dict, List, Tuple

from agents import ContinuityKeeper, DraftSmith, LoreArchivist, PlotEngineer, SimulatedReader


def run_chapter_generation(loop) -> Dict[str, Any]:
    """
    阶段2–4：生成单章内容并回写。
    会更新 loop 上的 lore_records、story_history、cliffhanger、plot_arc_index 等，并落盘章节与 lore。
    """
    print("\n" + "=" * 60)
    print(f"生成第 {loop.current_chapter_num} 章")
    print("=" * 60)

    full_story_history = "\n".join(loop.story_history) if loop.story_history else ""
    lore_context = _build_lore_context(loop)
    story_history_for_draft = full_story_history + ("\n\n" + lore_context if lore_context else "")

    print("\n[阶段2] 策划与编剧")
    print("\n[C] 情景工程师正在规划剧情...")
    chapter_outline, plot_analysis, plot_data = _ensure_plot_arc(loop, full_story_history)
    print(f"✓ 剧情大纲已生成: {chapter_outline.get('title', '未命名')}")

    plot_data_for_draft = _plot_data_for_draft(loop, chapter_outline)
    raw_text, chapter_title = _run_draft(loop, chapter_outline, plot_analysis, plot_data_for_draft, story_history_for_draft)
    print(f"✓ 正文初稿已生成: {chapter_title}")

    print("\n[阶段3] 质检与风控")
    audit_passed, raw_text, chapter_title, plot_data = _run_audit_phase(
        loop, raw_text, chapter_title, chapter_outline, plot_analysis, plot_data_for_draft,
        story_history_for_draft, full_story_history, plot_data,
    )
    if not audit_passed:
        raise RuntimeError("章节生成失败，已重试 3 次")

    print("\n[阶段4] 数据回写")
    _run_writeback(loop, chapter_title, raw_text, chapter_outline)

    if loop.plot_arc and loop.plot_arc_index < len(loop.plot_arc):
        loop.plot_arc_index += 1

    return {
        "chapter_num": loop.current_chapter_num,
        "title": chapter_title,
        "content": raw_text,
        "plot_data": plot_data,
    }


def _build_lore_context(loop) -> str:
    if not loop.lore_records:
        return ""
    lore_context = "相关历史设定：\n"
    for record in loop.lore_records[-5:]:
        try:
            record_data = json.loads(record.get("output_data", "{}"))
            summary = record_data.get("summary_text", "")
            if summary:
                lore_context += f"- {summary}\n"
        except Exception:
            continue
    return lore_context


def _participating_characters_for_outline(db_state: dict, chapter_outline: dict) -> List[dict]:
    participating_char_data = []
    if db_state.get("protagonist"):
        participating_char_data.append(db_state["protagonist"])
    participating_char_ids = chapter_outline.get("participating_characters", [])
    for char_id in participating_char_ids:
        for char_list in [db_state.get("supporting_characters", []), db_state.get("villains", [])]:
            for char in char_list:
                if char.get("id") == char_id:
                    participating_char_data.append(char)
                    break
    return participating_char_data


def _plot_data_for_draft(loop, chapter_outline: dict) -> dict:
    db_state = loop.db.get_state()
    participating_char_data = _participating_characters_for_outline(db_state, chapter_outline)
    participating_characters_json = json.dumps(participating_char_data, ensure_ascii=False, indent=2)
    return {
        "location_id": chapter_outline.get("location_id", ""),
        "plot_points": json.dumps(chapter_outline.get("plot_points", []), ensure_ascii=False),
        "participating_characters": participating_characters_json,
        "key_items_used": json.dumps(chapter_outline.get("key_items_used", []), ensure_ascii=False),
        "chapter_num": chapter_outline.get("chapter_num", loop.current_chapter_num),
        "expected_reader_reaction": chapter_outline.get("expected_reader_reaction", ""),
        "emotional_tone": chapter_outline.get("emotional_tone", ""),
        "cliffhanger": chapter_outline.get("cliffhanger", ""),
    }


def _parse_draft_result(draft_result: dict, current_chapter_num: int) -> Tuple[str, str]:
    raw_text = draft_result.get("draft_content", "")
    chapter_title = draft_result.get("title", f"第{current_chapter_num}章")
    if not raw_text:
        try:
            draft_data_str = draft_result.get("element_data", "")
            if draft_data_str:
                draft_data = json.loads(draft_data_str)
                raw_text = draft_data.get("draft_content", "")
                chapter_title = draft_data.get("title", chapter_title)
        except Exception:
            pass
    return raw_text, chapter_title


def _ensure_plot_arc(loop, full_story_history: str) -> Tuple[dict, str, dict]:
    plot_data: dict = {}
    if not loop.plot_arc:
        print("✓ 当前没有可用的 plot_arc，调用剧情工程师生成...")
        plot_engineer = PlotEngineer(
            world_setting=loop.get_novel_setting(),
            db_state=loop.db.get_state(),
            story_history=full_story_history,
        )
        plot_result = plot_engineer.run()
        plot_data_str = plot_result.get("element_data") or plot_result.get("output_data") or "{}"
        try:
            plot_data = json.loads(plot_data_str) if isinstance(plot_data_str, str) else (plot_data_str or {})
        except Exception:
            plot_data = {}
        loop.plot_arc = plot_data.get("plot_arc", []) or []
        loop.plot_arc_index = 0
        plot_analysis = plot_data.get("plot_analysis", "")
        if not loop.plot_arc:
            raise RuntimeError("情景工程师未生成有效的剧情大纲")
        try:
            with open(loop.book_dir / "plot_data.json", "w", encoding="utf-8") as f:
                json.dump(plot_data, f, ensure_ascii=False, indent=2)
            print(f"✓ 已生成并保存 plot_data.json（{len(loop.plot_arc)} 条）")
        except Exception:
            print("⚠ 已生成 plot_arc，但无法保存 plot_data.json 到磁盘")
        chapter_outline = loop.plot_arc[0]
        return chapter_outline, plot_analysis, plot_data

    chapter_outline = loop.plot_arc[loop.plot_arc_index]
    plot_analysis = ""
    try:
        with open(loop.book_dir / "plot_data.json", "r", encoding="utf-8") as f:
            saved = json.load(f)
            if isinstance(saved, dict):
                plot_analysis = saved.get("plot_analysis", "")
    except Exception:
        pass
    return chapter_outline, plot_analysis, plot_data


def _run_draft(loop, chapter_outline: dict, plot_analysis: str, plot_data_for_draft: dict, story_history_for_draft: str) -> Tuple[str, str]:
    print("\n[E] 正文塑造者正在创作正文...")
    draft_smith = DraftSmith(
        world_setting=loop.get_novel_setting(),
        db_state=loop.db.get_state(),
        story_history=story_history_for_draft,
        cliffhanger=loop.cliffhanger,
        plot_analysis=plot_analysis,
        plot_data=plot_data_for_draft,
    )
    draft_result = draft_smith.run()
    return _parse_draft_result(draft_result, loop.current_chapter_num)


def _run_audit_phase(
    loop,
    raw_text: str,
    chapter_title: str,
    chapter_outline: dict,
    plot_analysis: str,
    plot_data_for_draft: dict,
    story_history_for_draft: str,
    full_story_history: str,
    plot_data: dict,
) -> Tuple[bool, str, str, dict]:
    max_retries = 3
    retry_count = 0
    audit_passed = False

    while retry_count < max_retries and not audit_passed:
        print(f"\n[I] 毒舌书评人正在审核... (尝试 {retry_count + 1}/{max_retries})")
        simulated_reader = SimulatedReader(genre="玄幻/系统流", content_to_review=raw_text)
        review_result = simulated_reader.run()
        try:
            review_data = json.loads(review_result.get("output_data", "{}"))
        except Exception:
            review_data = {"decision": "PASS", "score": 3}

        decision = review_data.get("decision", "PASS")
        score = review_data.get("score", 3)

        if decision == "REWRITE" or score < 3:
            print(f"✗ 审核未通过 (评分: {score}/5)")
            print(f"  反馈: {review_data.get('review_summary', '无')}")
            if retry_count < max_retries - 1:
                raw_text, chapter_title, chapter_outline, plot_analysis, plot_data_for_draft, plot_data = _retry_after_review_fail(
                    loop, review_data, full_story_history, story_history_for_draft, plot_data,
                )
            retry_count += 1
            continue

        print(f"✓ 爽度审核通过 (评分: {score}/5)")
        print("\n[J] 连贯性守门员正在检查逻辑...")
        continuity_keeper = ContinuityKeeper(
            db_state=loop.db.get_state(),
            chapter_outline=json.dumps(chapter_outline, ensure_ascii=False),
            generated_text=raw_text,
        )
        continuity_result = continuity_keeper.run()
        try:
            continuity_data = json.loads(continuity_result.get("output_data", "{}"))
        except Exception:
            continuity_data = {"audit_result": "PASS"}

        audit_result = continuity_data.get("audit_result", "PASS")
        if audit_result == "FAIL":
            print("✗ 逻辑检查未通过")
            print(f"  错误: {continuity_data.get('review_comments', '无')}")
            if retry_count < max_retries - 1:
                print("  → 重新生成正文...")
                raw_text, chapter_title = _run_draft(loop, chapter_outline, plot_analysis, plot_data_for_draft, story_history_for_draft)
            retry_count += 1
            continue

        print("✓ 逻辑检查通过")
        audit_passed = True
        database_updates = continuity_data.get("database_updates") or {}
        if database_updates:
            print("  → 更新数据库状态...")
            try:
                loop.db.update(database_updates)
            except Exception as e:
                print(f"⚠ 更新数据库时出错: {e}")

    return audit_passed, raw_text, chapter_title, plot_data


def _retry_after_review_fail(
    loop, review_data: dict, full_story_history: str, story_history_for_draft: str,
) -> Tuple[str, str, dict, str, dict]:
    print("  → 重新规划剧情大纲...")
    feedback_text = "\n".join(review_data.get("improvement_suggestions", []))
    full_story_history_with_feedback = f"{full_story_history}\n\n反馈意见：\n{feedback_text}"
    plot_engineer = PlotEngineer(
        world_setting=loop.get_novel_setting(),
        db_state=loop.db.get_state(),
        story_history=full_story_history_with_feedback,
    )
    plot_result = plot_engineer.run()
    plot_data_str = plot_result.get("element_data") or "{}"
    try:
        plot_data = json.loads(plot_data_str) if isinstance(plot_data_str, str) else (plot_data_str or {})
    except Exception:
        plot_data = {}
    new_plot_arc = plot_data.get("plot_arc", [])
    if new_plot_arc:
        try:
            with open(loop.book_dir / "plot_data.json", "w", encoding="utf-8") as f:
                json.dump(plot_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        loop.plot_arc = new_plot_arc
        loop.plot_arc_index = 0
        chapter_outline = loop.plot_arc[0]
        plot_analysis = plot_data.get("plot_analysis", "")
        plot_data_for_draft = _plot_data_for_draft(loop, chapter_outline)
        raw_text, chapter_title = _run_draft(loop, chapter_outline, plot_analysis, plot_data_for_draft, story_history_for_draft)
        return raw_text, chapter_title, chapter_outline, plot_analysis, plot_data_for_draft, plot_data
    return "", "", {}, "", {}, plot_data


def _run_writeback(loop, chapter_title: str, raw_text: str, chapter_outline: dict) -> None:
    print("\n[G] 历史档案馆正在归档...")
    lore_archivist = LoreArchivist(
        chapter_num=loop.current_chapter_num,
        chapter_title=chapter_title,
        final_chapter_text=raw_text,
    )
    lore_result = lore_archivist.run()
    loop.lore_records.append(lore_result)

    lore_file = loop.book_dir / f"lore_record_ch{loop.current_chapter_num}.json"
    with open(lore_file, "w", encoding="utf-8") as f:
        f.write(lore_result.get("output_data", "{}"))
    print(f"✓ 历史记录已保存: {lore_file}")

    try:
        lore_data = json.loads(lore_result.get("output_data", "{}"))
        summary = lore_data.get("summary_text", "")
        if summary:
            loop.story_history.append(summary)
    except Exception:
        pass

    try:
        lore_data = json.loads(lore_result.get("output_data", "{}"))
        plot_threads = lore_data.get("plot_threads", {})
        opened_threads = plot_threads.get("opened", [])
        if opened_threads:
            loop.cliffhanger = opened_threads[-1].get("description", "")
    except Exception:
        loop.cliffhanger = chapter_outline.get("cliffhanger", "")

    chapter_file = loop.book_dir / f"chapter_{loop.current_chapter_num:03d}.md"
    with open(chapter_file, "w", encoding="utf-8") as f:
        f.write(f"# {chapter_title}\n\n")
        f.write(raw_text)
    print(f"✓ 章节已保存: {chapter_file}")
