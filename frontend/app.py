from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import streamlit as st

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config import GEMINI_API_KEY
from frontend.services import (
    create_book_with_initialization,
    create_prompt_preset_copy,
    create_short_story_outline,
    delete_book,
    generate_chapter_with_outline,
    generate_short_story_chapter,
    get_book_health_report,
    get_chapter_outline_preview,
    get_database_table,
    get_book_view,
    get_generation_state_history,
    get_llm_run_log_history,
    get_prompt_preset_detail,
    get_short_story_view_service,
    list_books,
    list_database_tables,
    list_prompt_preset_summaries,
    list_short_stories_service,
    matching_lore_for_chapter,
    read_artifact_text,
    regenerate_artifact,
    is_regeneratable_artifact,
    rewrite_chapter_fragment,
    run_book_action,
    save_artifact_text,
    save_chapter_outline_override,
    save_database_table,
    save_prompt_template_config,
    update_book_prompt_preset,
    update_prompt_preset_info,
)


st.set_page_config(page_title="Auto Novel X 控制台", layout="wide")
PROMPT_EDITOR_OPEN_KEY = "prompt-editor-open"


def main() -> None:
    st.title("Auto Novel X 创作控制台")
    if not GEMINI_API_KEY:
        st.warning("未检测到 GEMINI_API_KEY。当前可以浏览和编辑产物，但生成相关按钮会被禁用。")

    live_log_placeholder = st.empty()
    _render_prompt_editor_button()
    output_dir = st.sidebar.text_input("输出目录", value="output")

    # ── 顶层模式切换 ──────────────────────────────────────────────────────────
    mode_tabs = st.tabs(["📖 小说", "📝 短故事"])

    with mode_tabs[0]:
        _render_novel_mode(output_dir, live_log_placeholder)

    with mode_tabs[1]:
        _render_short_story_tab(output_dir, live_log_placeholder)


def _render_novel_mode(output_dir: str, live_log_placeholder) -> None:
    """原有小说模式——原样保留。"""
    prompt_presets = list_prompt_preset_summaries()
    books = list_books(output_dir)

    _render_create_book_form(output_dir, live_log_placeholder, prompt_presets)

    if not books:
        st.info("还没有检测到书籍目录。先在左侧创建一本新书。")
        _render_last_action()
        _maybe_render_prompt_editor_dialog(None, None, prompt_presets)
        return

    selected_book_path = _render_book_selector(books)
    if not selected_book_path:
        st.info("请选择一本书。")
        _render_last_action()
        _maybe_render_prompt_editor_dialog(None, None, prompt_presets)
        return

    book_view = get_book_view(selected_book_path)
    summary = book_view["summary"]

    _maybe_render_prompt_editor_dialog(selected_book_path, book_view, prompt_presets)

    st.subheader(summary["title"])
    if summary.get("tagline"):
        st.caption(summary["tagline"])
    if summary.get("label_line"):
        st.markdown(f"**{summary['label_line']}**")
    st.write(summary["logline"] or "暂无一句话简介。")
    if summary.get("blurb"):
        st.markdown(summary["blurb"])
    if summary.get("mini_theater"):
        with st.expander("小剧场"):
            st.markdown(summary["mini_theater"])

    _render_metrics(summary)
    _render_action_bar(
        selected_book_path,
        summary.get("main_story_goal", ""),
        summary.get("prompt_preset_id", "default"),
        live_log_placeholder,
    )
    _render_last_action()

    tabs = st.tabs(["总览", "生成控制", "章节阅读", "产物编辑", "数据库", "健康检查/日志", "Prompt 配置", "书籍操作"])
    with tabs[0]:
        _render_overview(book_view)
    with tabs[1]:
        _render_generation_tab(
            selected_book_path,
            summary.get("main_story_goal", ""),
            summary.get("prompt_preset_id", "default"),
            live_log_placeholder,
        )
    with tabs[2]:
        _render_chapter_reader(selected_book_path, book_view)
    with tabs[3]:
        _render_artifact_editor(selected_book_path, book_view, live_log_placeholder)
    with tabs[4]:
        _render_database_tab(selected_book_path, book_view)
    with tabs[5]:
        _render_health_and_logs_tab(selected_book_path)
    with tabs[6]:
        _render_prompt_binding_tab(selected_book_path, book_view, prompt_presets)
    with tabs[7]:
        _render_book_operations_tab(selected_book_path, book_view)


def _render_create_book_form(output_dir: str, live_log_placeholder, prompt_presets: list[dict[str, Any]]) -> None:
    with st.sidebar.expander("新建书籍", expanded=False):
        prompt_options = [preset["id"] for preset in prompt_presets]
        with st.form("create-book-form", clear_on_submit=False):
            human_idea = st.text_area("核心创意", height=140, placeholder="主角设定、题材组合、卖点……")
            main_story_goal = st.text_input("全书目标", placeholder="例如：成仙、复仇、建立宗门")
            trend_analysis = st.text_area("趋势分析 JSON（可选）", height=120)
            prompt_preset_id = st.selectbox(
                "Prompt 预设",
                options=prompt_options,
                index=_default_prompt_preset_index(prompt_options),
                format_func=lambda value: _prompt_preset_label(value, prompt_presets),
            )
            submitted = st.form_submit_button("创建并初始化", disabled=not GEMINI_API_KEY)

        if submitted:
            try:
                result = _run_live_action(
                    live_log_placeholder,
                    heading="正在初始化书籍...",
                    runner=lambda log_callback: create_book_with_initialization(
                        output_dir=output_dir,
                        human_idea=human_idea,
                        main_story_goal=main_story_goal,
                        trend_analysis_text=trend_analysis,
                        prompt_preset_id=prompt_preset_id,
                        log_callback=log_callback,
                    ),
                )
            except Exception as exc:
                _set_last_action(
                    kind="error",
                    message=str(exc),
                    logs=traceback.format_exc(),
                )
            else:
                _set_last_action_result(result)
                payload = result.payload or {}
                if payload.get("book_dir"):
                    st.session_state["selected_book_path"] = payload["book_dir"]
                st.rerun()


def _render_prompt_editor_button() -> None:
    if st.sidebar.button("Prompt 编辑", use_container_width=True, type="secondary"):
        st.session_state[PROMPT_EDITOR_OPEN_KEY] = True
    st.sidebar.markdown("---")


def _maybe_render_prompt_editor_dialog(book_path: str | None, book_view: dict | None, prompt_presets: list[dict[str, Any]]) -> None:
    if not st.session_state.get(PROMPT_EDITOR_OPEN_KEY):
        return
    st.session_state[PROMPT_EDITOR_OPEN_KEY] = False
    _render_prompt_editor_dialog(book_path, book_view, prompt_presets)


@st.dialog("Prompt 编辑", width="large")
def _render_prompt_editor_dialog(book_path: str | None, book_view: dict | None, prompt_presets: list[dict[str, Any]]) -> None:
    _render_prompt_editor(book_path, book_view, prompt_presets)
    if st.button("关闭", key="prompt-editor-close", use_container_width=True):
        st.rerun()


def _render_short_story_tab(output_dir: str, live_log_placeholder) -> None:
    """短故事模式：新建大纲 → 分步确认 → 逐章生成。"""
    st.markdown("### 📝 短故事")
    stories = list_short_stories_service(output_dir)

    # ── 新建短故事 ────────────────────────────────────────────────────────────
    with st.expander("🆕 新建短故事", expanded=not stories):
        track = st.radio("创作轨道", ["A — IP回响（文艺深度，30k-50k字）", "B — 高流量爆款（6k-80k字）"],
                         key="ss-track", horizontal=True)
        track_char = "A" if track.startswith("A") else "B"
        target_words = st.number_input("预期总字数", min_value=6000, max_value=80000, value=20000, step=1000, key="ss-words")
        inspiration = st.text_area("初始灵感/关键词", height=100, key="ss-inspiration",
                                   placeholder="例如：现代女企业家穿越明朝，用商业思维降维打击权贵")
        outline_log = st.empty()
        if st.button("生成大纲", key="ss-gen-outline", disabled=not GEMINI_API_KEY or not inspiration.strip()):
            try:
                result = _run_live_action(
                    outline_log, heading="正在生成大纲...",
                    runner=lambda lc: create_short_story_outline(
                        output_dir, track_char, int(target_words), inspiration, log_callback=lc))
            except Exception as exc:
                _set_last_action(kind="error", message=str(exc), logs=traceback.format_exc())
            else:
                _set_last_action_result(result)
            st.rerun()

    _render_last_action()

    if not stories:
        return

    # ── 选择已有短故事 ─────────────────────────────────────────────────────────
    st.markdown("---")
    story_opts = {s["path"]: f"《{s['title']}》 轨道{s['track']} {s['completed_chapters']}/{s['total_chapters']}章" for s in stories}
    selected_path = st.selectbox("选择短故事", options=list(story_opts.keys()),
                                 format_func=lambda p: story_opts[p], key="ss-selector")
    if not selected_path:
        return

    view = get_short_story_view_service(selected_path)
    meta = view["meta"]
    outline = view["outline"]

    col1, col2, col3 = st.columns(3)
    col1.metric("轨道", f"{'A — IP回响' if meta.get('track')=='A' else 'B — 高流量'}")
    col2.metric("进度", f"{meta.get('completed_chapters',0)} / {meta.get('total_chapters',0)} 章")
    col3.metric("目标字数", f"{meta.get('target_words',0):,}")

    if outline.get("logline"):
        st.caption(f"**一句话简介**：{outline['logline']}")
    if outline.get("market_validation"):
        st.caption(f"**市场校验**：{outline['market_validation']}")

    # ── 大纲预览 + 生成下一章 ──────────────────────────────────────────────────
    tabs = st.tabs(["📋 大纲", "📖 阅读", "⭐ 质检报告"])

    with tabs[0]:
        chapters_data = outline.get("chapters", [])
        for ch in chapters_data:
            n = ch.get("chapter_num", "?")
            done = n <= meta.get("completed_chapters", 0)
            icon = "✅" if done else "⬜"
            with st.expander(f"{icon} 第{n}章《{ch.get('title', '')}》 ~{ch.get('estimated_words',0)}字", expanded=False):
                st.write(ch.get("outline", ""))
                st.caption(f"🎯 {ch.get('hook', '')}")

        next_ch = meta.get("completed_chapters", 0) + 1
        if next_ch <= meta.get("total_chapters", 0):
            ch_log = st.empty()
            if st.button(f"▶ 生成第{next_ch}章", key=f"ss-gen-ch-{selected_path}",
                         disabled=not GEMINI_API_KEY, type="primary"):
                try:
                    result = _run_live_action(
                        ch_log, heading=f"正在生成第{next_ch}章...",
                        runner=lambda lc: generate_short_story_chapter(selected_path, next_ch, log_callback=lc))
                except Exception as exc:
                    _set_last_action(kind="error", message=str(exc), logs=traceback.format_exc())
                else:
                    _set_last_action_result(result)
                st.rerun()
        else:
            st.success("🎉 全部章节已生成完毕！")

    with tabs[1]:
        chapter_files = view.get("chapters", [])
        if not chapter_files:
            st.info("还没有生成任何章节。")
        else:
            sel_ch = st.selectbox("选择章节", [c["name"] for c in chapter_files], key=f"ss-read-{selected_path}")
            if sel_ch:
                ch_path = next(c["path"] for c in chapter_files if c["name"] == sel_ch)
                st.markdown(Path(ch_path).read_text(encoding="utf-8"))

    with tabs[2]:
        review_files = view.get("reviews", [])
        if not review_files:
            st.info("还没有质检报告。")
        else:
            sel_rv = st.selectbox("选择质检报告", [r["name"] for r in review_files], key=f"ss-review-{selected_path}")
            if sel_rv:
                rv_path = next(r["path"] for r in review_files if r["name"] == sel_rv)
                import json as _json
                rv = _json.loads(Path(rv_path).read_text(encoding="utf-8"))
                passed = rv.get("pass_gate", False)
                st.markdown(f"**质检结果**：{'✅ 通过' if passed else '❌ 未通过'}")
                scores = rv.get("metrics_scores", {})
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("节奏紧凑", scores.get("pacing", "-"))
                c2.metric("剧情跌宕", scores.get("plot_twists", "-"))
                c3.metric("情感张力", scores.get("emotional_tension", "-"))
                c4.metric("沉浸感", scores.get("immersion", "-"))
                cp = rv.get("commercial_potential", {})
                st.caption(f"改编方向：{cp.get('best_adaptation_format','-')} | 激励活动：{cp.get('target_incentive_plan','-')}")
                if not passed and rv.get("feedback_for_rewrite"):
                    st.warning(rv["feedback_for_rewrite"])

    # ── Prompt 配置 ────────────────────────────────────────────────────────────
    _render_short_story_prompt_editor()


def _render_short_story_prompt_editor() -> None:
    PROMPT_DIR = Path(__file__).parent.parent / "prompt_presets" / "short_story"
    AGENTS = [
        ("outline_concept_prompt", "📋 选题大纲策划"),
        ("content_generation_prompt", "✍️ 正文创作"),
        ("review_alignment_prompt", "⭐ 合规评估"),
    ]
    with st.expander("⚙️ 短故事 Prompt 配置", expanded=False):
        for fname, label in AGENTS:
            fpath = PROMPT_DIR / f"{fname}.json"
            data = json.loads(fpath.read_text(encoding="utf-8"))
            st.markdown(f"**{label}**")
            with st.form(key=f"ss-prompt-{fname}"):
                new_sys = st.text_area("system_prompt", value=data.get("system_prompt", ""), height=200, key=f"{fname}-sys")
                new_usr = st.text_area("user_prompt", value=data.get("user_prompt", ""), height=150, key=f"{fname}-usr")
                if st.form_submit_button("保存"):
                    data["system_prompt"] = new_sys
                    data["user_prompt"] = new_usr
                    fpath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    st.success(f"{label} 已保存")
            st.divider()


def _render_book_selector(books) -> str | None:
    book_map = {summary.path: summary for summary in books}
    selected = st.sidebar.selectbox(
        "选择书籍",
        options=list(book_map.keys()),
        index=_default_book_index(list(book_map.keys())),
        format_func=lambda path: f"{book_map[path].title} ({book_map[path].chapter_count} 章)",
    )
    # 切换书籍时清空目标输入的 session_state，避免复用上一本的全书目标
    prev = st.session_state.get("selected_book_path")
    if prev != selected:
        for key in ("tab-main-story-goal", "sidebar-main-story-goal"):
            st.session_state.pop(key, None)
    st.session_state["selected_book_path"] = selected
    return selected


def _render_metrics(summary: dict) -> None:
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("章节数", summary["chapter_count"])
    col2.metric("卷数", summary["volume_count"])
    col3.metric("产物数", summary["artifact_count"])
    col4.metric("最近更新", summary["updated_at"])
    col5.metric("Prompt 预设", summary.get("prompt_preset_name", "默认"))


def _render_action_bar(book_path: str, default_goal: str, prompt_preset_id: str, live_log_placeholder) -> None:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 快速控制")
    goal = st.sidebar.text_input("生成时使用的全书目标", value=default_goal, key=f"sidebar-main-story-goal-{hash(book_path)}")
    st.sidebar.caption(f"当前 Prompt 预设：{prompt_preset_id}")

    col1, col2 = st.sidebar.columns(2)
    if col1.button("生成下一章", use_container_width=True, disabled=not GEMINI_API_KEY):
        _run_action(book_path, "generate_chapter", goal, prompt_preset_id, live_log_placeholder)
    if col2.button("开始新卷", use_container_width=True, disabled=not GEMINI_API_KEY):
        _run_action(book_path, "start_new_volume", goal, prompt_preset_id, live_log_placeholder)


def _render_generation_tab(book_path: str, default_goal: str, prompt_preset_id: str, live_log_placeholder) -> None:
    st.markdown("### 生成控制")
    st.caption(f"当前书籍将使用 Prompt 预设：{prompt_preset_id}")

    goal = st.text_input("全书目标", value=default_goal, key=f"tab-main-story-goal-{hash(book_path)}")

    # ── 两步生成：先预览细纲，确认后再生成正文 ──────────────────────────────
    st.markdown("#### 生成下一章（推荐：先预览细纲）")
    pending_key = "pending_chapter_outline"

    col_preview, col_confirm, col_skip = st.columns(3)
    if col_preview.button("① 预览细纲", key="btn-preview-outline",
                          use_container_width=True, disabled=not GEMINI_API_KEY):
        try:
            result = _run_live_action(
                live_log_placeholder,
                heading="正在生成细化大纲...",
                runner=lambda log_callback: get_chapter_outline_preview(
                    book_path, prompt_preset_id=prompt_preset_id
                ),
            )
            if result.success and result.payload and result.payload.get("outline_text"):
                outline = str(result.payload["outline_text"]).strip()
                if len(outline) > 0 and len(outline) < 50000:  # 防止超大文本卡死前端
                    st.session_state[pending_key] = outline
                else:
                    _set_last_action(kind="error", message=f"细纲异常：长度 {len(outline)}，超出合理范围", logs=result.logs)
            else:
                _set_last_action(kind="error", message=result.message, logs=result.logs)
        except Exception as e:
            _set_last_action(kind="error", message=f"预览细纲时发生错误：{type(e).__name__}: {str(e)[:200]}", logs=[])
            import traceback
            traceback.print_exc()
        st.rerun()

    if col_skip.button("直接生成（不预览细纲）", key="tab-generate-chapter",
                       use_container_width=True, disabled=not GEMINI_API_KEY):
        st.session_state.pop(pending_key, None)
        _run_action(book_path, "generate_chapter", goal, prompt_preset_id, live_log_placeholder)

    # 细纲预览 / 编辑区
    if pending_key in st.session_state:
        st.markdown("##### 细化大纲（可直接编辑后确认）")
        try:
            outline_value = str(st.session_state.get(pending_key, ""))
            if not outline_value or len(outline_value) > 100000:
                st.error(f"细纲数据异常（长度 {len(outline_value)}），已清空")
                st.session_state.pop(pending_key, None)
                st.rerun()
        except Exception as e:
            st.error(f"加载细纲失败：{e}")
            st.session_state.pop(pending_key, None)
            st.rerun()

        edited = st.text_area(
            "编辑细化大纲",
            value=outline_value,
            height=420,
            key="outline-edit-area",
            label_visibility="collapsed",
        )
        c1, c2 = st.columns(2)
        if c1.button("② 确认，按此大纲生成正文", key="btn-confirm-outline",
                     use_container_width=True, disabled=not GEMINI_API_KEY, type="primary"):
            try:
                result = _run_live_action(
                    live_log_placeholder,
                    heading="正在按细化大纲生成正文...",
                    runner=lambda log_callback: generate_chapter_with_outline(
                        book_path,
                        outline_text=edited,
                        main_story_goal=goal,
                        prompt_preset_id=prompt_preset_id,
                        log_callback=log_callback,
                    ),
                )
            except Exception as exc:
                _set_last_action(kind="error", message=str(exc), logs=traceback.format_exc())
            else:
                _set_last_action_result(result)
            st.session_state.pop(pending_key, None)
            st.rerun()
        if c2.button("保存细纲修改", key="btn-save-outline", use_container_width=True):
            try:
                save_result = save_chapter_outline_override(book_path, edited)
                _set_last_action(kind="success" if save_result.success else "error",
                                 message=save_result.message, logs=save_result.logs)
            except Exception as exc:
                _set_last_action(kind="error", message=str(exc), logs=traceback.format_exc())
            st.rerun()
        if st.button("放弃细纲", key="btn-discard-outline"):
            st.session_state.pop(pending_key, None)
            st.rerun()

    # ── 开始新卷 / 手动连续生成（保留原有功能）──────────────────────────────
    st.markdown("---")
    col_newvol, _ = st.columns(2)
    if col_newvol.button("开始新卷", key="tab-start-new-volume",
                         use_container_width=True, disabled=not GEMINI_API_KEY):
        _run_action(book_path, "start_new_volume", goal, prompt_preset_id, live_log_placeholder)

    st.markdown("#### 手动连续生成")
    st.caption("适合想一次推进少量章节时使用。数量限制为 2-5 章，系统会逐章沿用现有工作流。")
    batch_col1, batch_col2 = st.columns([1, 2])
    chapter_count = batch_col1.number_input(
        "连续生成章数", min_value=2, max_value=5, value=2, step=1, key="tab-generate-chapter-count",
    )
    if batch_col2.button("按数量连续生成", key="tab-generate-chapters",
                         use_container_width=True, disabled=not GEMINI_API_KEY):
        _run_action(
            book_path, "generate_chapters", goal, prompt_preset_id, live_log_placeholder,
            chapter_count=int(chapter_count),
        )


def _render_overview(book_view: dict) -> None:
    world_setting = book_view["world_setting"]
    novel_setting = world_setting.get("novel_setting", {}) if isinstance(world_setting, dict) else {}
    business = world_setting.get("business_analysis", {}) if isinstance(world_setting, dict) else {}
    db_state = book_view["db_state"]

    left, right = st.columns([1.2, 1])
    with left:
        st.markdown("#### 世界观与商业定位")
        st.json(
            {
                "book_title": business.get("book_title", ""),
                "selected_genre": business.get("selected_genre", ""),
                "tagline": business.get("tagline", ""),
                "logline": business.get("logline", ""),
                "blurb": business.get("blurb", ""),
                "unique_selling_point": business.get("unique_selling_point", ""),
                "click_moment": business.get("click_moment", ""),
                "prompt_preset": book_view.get("prompt_preset", {}),
                "golden_finger": novel_setting.get("golden_finger", {}),
                "reader_expectation": novel_setting.get("reader_expectation", {}),
                "ending_blueprint": novel_setting.get("ending_blueprint", {}),
            }
        )
    with right:
        protagonist = db_state.get("protagonist", {})
        st.markdown("#### 当前主角状态")
        st.json(protagonist or {"message": "数据库中暂无主角数据"})

    st.markdown("#### 产物目录")
    for category, items in book_view["artifact_catalog"].items():
        if not items:
            continue
        with st.expander(f"{category} ({len(items)})", expanded=category in {"核心设定", "章节正文"}):
            for item in items:
                st.code(item, language="text")


def _render_chapter_reader(book_path: str, book_view: dict) -> None:
    chapter_options = book_view["chapter_options"]
    if not chapter_options:
        st.info("当前还没有章节。")
        return

    option_map = {item["path"]: item["label"] for item in chapter_options}
    selected_chapter = st.selectbox(
        "选择章节",
        options=list(option_map.keys()),
        format_func=lambda value: option_map[value],
        key="chapter-reader-select",
    )
    chapter_content = read_artifact_text(book_path, selected_chapter)
    related_lore = matching_lore_for_chapter(book_path, selected_chapter)
    chapter_word_count = _chapter_character_count(chapter_content)

    left, right = st.columns([1.3, 1])
    with left:
        st.markdown(f"#### 阅读视图 <span style='font-size:0.9rem;font-weight:400;color:#6b7280;'>（约 {chapter_word_count} 字）</span>", unsafe_allow_html=True)
        st.markdown(chapter_content)
    with right:
        if related_lore:
            st.markdown("#### 对应档案")
            lore_content = read_artifact_text(book_path, related_lore)
            try:
                lore = json.loads(lore_content)
                if lore.get("summary_text"):
                    st.caption("**本章摘要**")
                    st.write(lore["summary_text"])
                if lore.get("semantic_tags"):
                    st.caption("**标签**：" + " · ".join(lore["semantic_tags"]))
                if lore.get("character_status_changes"):
                    st.caption("**人物状态变化**")
                    for line in lore["character_status_changes"]:
                        st.write(f"- {line}")
                opened = (lore.get("plot_threads") or {}).get("opened", [])
                if opened:
                    st.caption("**新开线索**")
                    for t in opened:
                        st.write(f"- {t.get('description', '')}")
                with st.expander("完整档案 JSON", expanded=False):
                    st.json(lore)
            except json.JSONDecodeError:
                st.code(lore_content, language="json")
        with st.expander("原始 Markdown（复制用）", expanded=False):
            st.code(chapter_content, language="markdown")
        _render_fragment_rewrite(book_path, selected_chapter)




def _render_fragment_rewrite(book_path: str, selected_chapter: str) -> None:
    with st.expander("✏️ 局部重写（选中片段 + 修改意见）", expanded=False):
        st.caption("从正文中复制不满意的段落，粘贴到下方，填写修改意见后点击局部重写。")
        fragment = st.text_area("需要修改的片段（从正文完整复制）", height=160, key=f"frag-{selected_chapter}")
        instruction = st.text_input("修改意见", placeholder="例如：男主反应太速食，改为控制欲波动而非直给", key=f"instr-{selected_chapter}")
        log_area = st.empty()
        if st.button("局部重写", key=f"frag-rewrite-{selected_chapter}", disabled=not GEMINI_API_KEY or not fragment.strip()):
            if not instruction.strip():
                st.warning("请填写修改意见。")
            else:
                try:
                    result = _run_live_action(
                        log_area, heading="局部重写中...",
                        runner=lambda lc: rewrite_chapter_fragment(
                            book_path, selected_chapter, fragment, instruction,
                            prompt_preset_id=st.session_state.get(f"book-preset-{hash(book_path)}", ""),
                            log_callback=lc,
                        ),
                    )
                except Exception as exc:
                    _set_last_action(kind="error", message=str(exc), logs=traceback.format_exc())
                else:
                    _set_last_action_result(result)
                st.rerun()


def _chapter_character_count(chapter_content: str) -> int:
    content_lines = chapter_content.splitlines()
    if content_lines and content_lines[0].lstrip().startswith("#"):
        content_lines = content_lines[1:]
    content = "".join(content_lines)
    return sum(1 for char in content if not char.isspace())


def _render_artifact_editor(book_path: str, book_view: dict, live_log_placeholder) -> None:
    artifact_catalog = book_view["artifact_catalog"]
    artifact_options: list[str] = []
    labels: dict[str, str] = {}
    for category, items in artifact_catalog.items():
        if category == "数据库":
            continue
        for item in items:
            artifact_options.append(item)
            labels[item] = f"[{category}] {item}"

    if not artifact_options:
        st.info("没有可编辑的产物。")
        return

    selected_artifact = st.selectbox(
        "选择产物",
        options=artifact_options,
        format_func=lambda value: labels[value],
        key="artifact-editor-select",
    )
    if selected_artifact == "element_data.json":
        st.warning("element_data.json 是旧版元素快照，当前角色/地点/物品以数据库 tab 中的 database.db 状态为准。")
    artifact_content = read_artifact_text(book_path, selected_artifact)

    with st.form("artifact-editor-form"):
        edited_content = st.text_area("编辑内容", value=artifact_content, height=560)
        submitted = st.form_submit_button("保存产物")

    preview_left, preview_right = st.columns(2)
    with preview_left:
        st.markdown("#### 文件预览")
        if selected_artifact.endswith(".json"):
            try:
                st.json(json.loads(edited_content))
            except json.JSONDecodeError as exc:
                st.error(f"JSON 格式错误：{exc}")
        elif selected_artifact.endswith(".md"):
            st.markdown(edited_content)
        else:
            st.code(edited_content, language="text")
    with preview_right:
        st.markdown("#### 文件信息")
        st.code(selected_artifact, language="text")
        can_regen = is_regeneratable_artifact(selected_artifact)
        regenerate_clicked = st.button(
            "重新生成当前产物",
            key=f"artifact-regenerate-{selected_artifact}",
            use_container_width=True,
            disabled=not can_regen,
        )
        if not can_regen:
            st.caption("仅支持重生成 world_setting.json / .md 和章节正文。")
        # 就近渲染实时日志：章节/总纲重生成是长任务，日志必须显示在按钮下方。
        # 全局 live_log_placeholder 在所有 tab 之上，在本 tab 内点击时用户看不到它刷新，
        # 会误以为"没执行"。这里用本地占位符让进度就近可见。
        regenerate_log_placeholder = st.empty()
        if regenerate_clicked:
            try:
                result = _run_live_action(
                    regenerate_log_placeholder,
                    heading=f"正在重生成 {selected_artifact}...",
                    runner=lambda log_callback: regenerate_artifact(
                        book_path,
                        selected_artifact,
                        prompt_preset_id=str(book_view.get("summary", {}).get("prompt_preset_id", "default")),
                        log_callback=log_callback,
                    ),
                )
            except Exception as exc:
                _set_last_action(
                    kind="error",
                    message=str(exc),
                    logs=traceback.format_exc(),
                )
            else:
                _set_last_action_result(result)
            st.rerun()

    if submitted:
        try:
            save_artifact_text(book_path, selected_artifact, edited_content)
        except Exception as exc:
            _set_last_action(
                kind="error",
                message=f"保存失败：{exc}",
                logs=traceback.format_exc(),
            )
        else:
            _set_last_action(kind="success", message=f"已保存 {selected_artifact}。", logs="")
            st.rerun()


def _render_database_tab(book_path: str, book_view: dict) -> None:
    db_state = book_view["db_state"]
    protagonist = db_state.get("protagonist", {})
    st.markdown("### 数据库总览")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("主角", 1 if protagonist else 0)
    col2.metric("配角", len(db_state.get("supporting_characters", [])))
    col3.metric("反派", len(db_state.get("villains", [])))
    col4.metric("地点 / 物品", f"{len(db_state.get('locations', []))} / {len(db_state.get('items', []))}")

    with st.expander("主角状态预览", expanded=True):
        st.json(protagonist or {"message": "暂无数据"})

    table_summaries = list_database_tables(book_path)
    table_options = [item["name"] for item in table_summaries]
    table_map = {item["name"]: item for item in table_summaries}
    selected_table = st.selectbox(
        "选择数据表",
        options=table_options,
        format_func=lambda value: f"{table_map[value]['label']} · {value} ({table_map[value]['row_count']} 行)",
        key="database-table-select",
    )
    table_data = get_database_table(book_path, selected_table)
    st.caption(
        "主键："
        + ", ".join(table_data["primary_key"])
        + ("；JSON 字段：" + ", ".join(table_data["json_columns"]) if table_data["json_columns"] else "")
    )

    edited_rows = st.data_editor(
        table_data["rows"],
        key=f"database-table-editor-{selected_table}",
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        disabled=table_data["readonly_columns"],
        column_config=_database_column_config(table_data),
    )

    col_save, col_reset = st.columns([1, 1])
    if col_save.button("保存表格变更", key=f"database-save-{selected_table}", type="primary", use_container_width=True):
        try:
            rows = _records_from_editor(edited_rows)
            result = save_database_table(book_path, selected_table, rows)
        except Exception as exc:
            _set_last_action(
                kind="error",
                message=f"数据库表保存失败：{exc}",
                logs=traceback.format_exc(),
            )
        else:
            _set_last_action(
                kind="success",
                message=f"已保存 {table_data['label']}：{result['saved_rows']} 行，删除 {result['deleted_rows']} 行。",
                logs="",
            )
            st.rerun()
    if col_reset.button("放弃未保存修改", key=f"database-reset-{selected_table}", use_container_width=True):
        st.rerun()

    with st.expander("全量运行态预览（只读）", expanded=False):
        st.json(db_state)


def _render_health_and_logs_tab(book_path: str) -> None:
    st.markdown("### 健康检查")
    report = get_book_health_report(book_path)
    summary = report["summary"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("状态", report["status"])
    col2.metric("错误", summary.get("error", 0))
    col3.metric("警告", summary.get("warning", 0))
    col4.metric("章节 / Lore", f"{summary.get('chapters', 0)} / {summary.get('lore_records', 0)}")

    if report["issues"]:
        st.dataframe(
            [
                {
                    "severity": item["severity"],
                    "code": item["code"],
                    "message": item["message"],
                    "detail": json.dumps(item.get("detail"), ensure_ascii=False) if item.get("detail") is not None else "",
                }
                for item in report["issues"]
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("当前未发现产物/数据库一致性问题。")

    st.markdown("### 章节生成状态")
    states = get_generation_state_history(book_path, limit=20)
    if states:
        selected_state = st.selectbox(
            "选择生成状态记录",
            options=list(range(len(states))),
            format_func=lambda index: f"{states[index].get('status', '')} · {states[index].get('run_id', states[index].get('path', ''))}",
            key="generation-state-select",
        )
        st.json(states[selected_state])
    else:
        st.info("暂无章节生成状态记录。")

    st.markdown("### LLM 调用日志")
    logs = get_llm_run_log_history(book_path, limit=20)
    if logs:
        selected_log = st.selectbox(
            "选择 LLM 调用日志",
            options=list(range(len(logs))),
            format_func=lambda index: (
                f"{logs[index].get('status', '')} · "
                f"{logs[index].get('operation', '')} · "
                f"{logs[index].get('caller', {}).get('function', '')} · "
                f"{logs[index].get('duration_ms', 0)}ms"
            ),
            key="llm-log-select",
        )
        log_detail = logs[selected_log]["detail"]
        st.caption(logs[selected_log]["path"])
        st.json(log_detail)
    else:
        st.info("暂无 LLM 调用日志。生成/初始化时会自动记录。")


def _database_column_config(table_data: dict[str, Any]) -> dict[str, Any]:
    config: dict[str, Any] = {}
    for column in table_data["primary_key"]:
        config[column] = st.column_config.TextColumn(column, help="主键字段，不能为空")
    for column in table_data["json_columns"]:
        config[column] = st.column_config.TextColumn(column, help="请输入合法 JSON", width="large")
    for column in table_data["integer_columns"]:
        config[column] = st.column_config.NumberColumn(column, step=1, format="%d")
    for column in table_data["readonly_columns"]:
        config[column] = st.column_config.TextColumn(column)
    return config


def _records_from_editor(value: Any) -> list[dict[str, Any]]:
    if hasattr(value, "to_dict"):
        return value.to_dict("records")
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _render_prompt_binding_tab(book_path: str, book_view: dict, prompt_presets: list[dict[str, Any]]) -> None:
    st.markdown("### 当前书籍 Prompt 配置")
    st.write("这里管理当前书籍绑定的 Prompt 预设；更细粒度的预设新建和模板编辑请使用侧边栏顶部的 Prompt 编辑按钮。")

    prompt_preset_ids = [preset["id"] for preset in prompt_presets]
    current_prompt_preset_id = str(book_view.get("summary", {}).get("prompt_preset_id", "default"))
    current_prompt_preset = book_view.get("prompt_preset", {})

    left, right = st.columns([1.1, 0.9])
    with left:
        st.markdown("#### 当前绑定")
        st.json(
            {
                "id": current_prompt_preset.get("id", current_prompt_preset_id),
                "name": current_prompt_preset.get("name", current_prompt_preset_id),
                "description": current_prompt_preset.get("description", ""),
                "source_preset_id": current_prompt_preset.get("source_preset_id", ""),
                "updated_at": current_prompt_preset.get("updated_at", ""),
            }
        )
    with right:
        with st.form("book-prompt-binding-tab-form"):
            selected_book_prompt_preset_id = st.selectbox(
                "切换当前书籍 Prompt 预设",
                options=prompt_preset_ids,
                index=_safe_index(prompt_preset_ids, current_prompt_preset_id),
                format_func=lambda value: _prompt_preset_label(value, prompt_presets),
                key="book-prompt-binding-tab-select",
            )
            bind_submitted = st.form_submit_button("保存当前书籍预设", use_container_width=True)

        if bind_submitted:
            try:
                update_book_prompt_preset(book_path, selected_book_prompt_preset_id)
            except Exception as exc:
                _set_last_action(kind="error", message=f"绑定 Prompt 预设失败：{exc}", logs=traceback.format_exc())
            else:
                _set_last_action(kind="success", message="已更新当前书籍的 Prompt 预设。", logs="")
                st.rerun()

        if st.button("打开 Prompt 编辑弹窗", key="open-prompt-editor-from-tab", use_container_width=True):
            st.session_state[PROMPT_EDITOR_OPEN_KEY] = True
            st.rerun()


def _render_book_operations_tab(book_path: str, book_view: dict) -> None:
    summary = book_view["summary"]
    st.markdown("### 书籍操作")
    st.write("这里集中放置书籍级操作。当前提供删除书籍，后续可继续扩展更多维护动作。")

    st.markdown("#### 当前书籍")
    st.json(
        {
            "title": summary["title"],
            "path": book_path,
            "chapter_count": summary["chapter_count"],
            "volume_count": summary["volume_count"],
            "artifact_count": summary["artifact_count"],
            "updated_at": summary["updated_at"],
        }
    )

    with st.expander("危险操作", expanded=True):
        st.warning("删除书籍会移除当前书籍目录下的全部章节、设定、数据库和日志文件，且无法恢复。")
        confirmed = st.checkbox(
            f"我确认删除《{summary['title']}》及其全部文件",
            key=f"confirm-delete-book-{summary['id']}",
        )
        if st.button(
            "删除书籍",
            key=f"delete-book-{summary['id']}",
            use_container_width=True,
            disabled=not confirmed,
        ):
            try:
                result = delete_book(book_path)
            except Exception as exc:
                _set_last_action(kind="error", message=f"删除书籍失败：{exc}", logs=traceback.format_exc())
            else:
                if st.session_state.get("selected_book_path") == book_path:
                    st.session_state.pop("selected_book_path", None)
                _set_last_action(kind="success", message=f"已删除书籍：{result['title']}。", logs="")
                st.rerun()


def _render_prompt_editor(book_path: str | None, book_view: dict | None, prompt_presets: list[dict[str, Any]]) -> None:
    st.markdown("### Prompt 预设工作区")
    st.write("可以在这里维护多套 agent Prompt，并编辑各套预设的具体模板。")

    prompt_preset_map = {preset["id"]: preset for preset in prompt_presets}
    prompt_preset_ids = list(prompt_preset_map.keys())

    with st.expander("新建 Prompt 预设", expanded=False):
        with st.form("create-prompt-preset-form"):
            preset_name = st.text_input("预设名称", placeholder="例如：冷峻黑暗流")
            preset_description = st.text_area("预设说明（可选）", height=100)
            source_preset_id = st.selectbox(
                "克隆来源",
                options=prompt_preset_ids,
                index=_default_prompt_preset_index(prompt_preset_ids),
                format_func=lambda value: _prompt_preset_label(value, prompt_presets),
                key="prompt-preset-source-select",
            )
            create_submitted = st.form_submit_button("创建预设")

        if create_submitted:
            try:
                created = create_prompt_preset_copy(
                    name=preset_name,
                    description=preset_description,
                    source_preset_id=source_preset_id,
                )
            except Exception as exc:
                _set_last_action(kind="error", message=f"创建 Prompt 预设失败：{exc}", logs=traceback.format_exc())
            else:
                st.session_state["prompt-editor-preset-id"] = created["meta"]["id"]
                _set_last_action(kind="success", message=f"已创建 Prompt 预设：{created['meta']['name']}。", logs="")
                st.rerun()

    selected_preset_id = st.selectbox(
        "编辑的 Prompt 预设",
        options=prompt_preset_ids,
        index=_default_prompt_editor_index(prompt_preset_ids, book_view),
        format_func=lambda value: _prompt_preset_label(value, prompt_presets),
        key="prompt-editor-preset-id",
    )
    preset_detail = get_prompt_preset_detail(selected_preset_id)
    preset_meta = preset_detail["meta"]

    with st.form("prompt-preset-meta-form"):
        preset_name = st.text_input(
            "预设名称",
            value=preset_meta.get("name", ""),
            disabled=selected_preset_id == "default",
        )
        preset_description = st.text_area("预设说明", value=preset_meta.get("description", ""), height=100)
        meta_submitted = st.form_submit_button("保存预设信息")

    if meta_submitted:
        try:
            update_prompt_preset_info(
                selected_preset_id,
                name=preset_name if selected_preset_id != "default" else None,
                description=preset_description,
            )
        except Exception as exc:
            _set_last_action(kind="error", message=f"保存预设信息失败：{exc}", logs=traceback.format_exc())
        else:
            _set_last_action(kind="success", message="已保存 Prompt 预设信息。", logs="")
            st.rerun()

    templates = preset_detail["templates"]
    template_names = list(templates.keys())
    if not template_names:
        st.error("当前 Prompt 预设没有加载到 Agent Prompt 模板。")
        st.json(
            {
                "selected_preset_id": selected_preset_id,
                "preset_detail_keys": list(preset_detail.keys()),
                "preset_meta": preset_meta,
            }
        )
        return

    st.caption(f"当前预设：{selected_preset_id}；可编辑模板数：{len(template_names)}")

    selected_template_name = st.selectbox(
        "选择 Agent Prompt",
        options=template_names,
        format_func=_format_template_name,
        key=f"prompt-template-select-{selected_preset_id}",
    )
    if selected_template_name not in templates:
        selected_template_name = template_names[0]
    template_config = templates[selected_template_name]

    st.caption("支持直接编辑 system/user prompt 文本，以及对应的 json schema。保存后，新绑定该预设的书籍会使用新版本。")

    with st.form("prompt-template-edit-form"):
        edited_config: dict[str, Any] = {}
        for field_name, field_value in template_config.items():
            label = _format_prompt_field_name(field_name)
            if field_name == "json_schema":
                edited_text = st.text_area(
                    label,
                    value=json.dumps(field_value, ensure_ascii=False, indent=2),
                    height=320,
                    key=f"prompt-field-{selected_preset_id}-{selected_template_name}-{field_name}",
                )
                edited_config[field_name] = edited_text
            else:
                edited_text = st.text_area(
                    label,
                    value=str(field_value),
                    height=220,
                    key=f"prompt-field-{selected_preset_id}-{selected_template_name}-{field_name}",
                )
                edited_config[field_name] = edited_text

        template_submitted = st.form_submit_button("保存当前模板")

    if template_submitted:
        try:
            normalized_config = {}
            for field_name, field_value in edited_config.items():
                if field_name == "json_schema":
                    normalized_config[field_name] = json.loads(field_value)
                else:
                    normalized_config[field_name] = field_value
            save_prompt_template_config(selected_preset_id, selected_template_name, normalized_config)
        except Exception as exc:
            _set_last_action(kind="error", message=f"保存 Prompt 模板失败：{exc}", logs=traceback.format_exc())
        else:
            _set_last_action(kind="success", message=f"已保存 {_format_template_name(selected_template_name)}。", logs="")
            st.rerun()


def _render_last_action() -> None:
    action = st.session_state.get("last_action")
    if not action:
        return

    if action["kind"] == "success":
        st.success(action["message"])
    else:
        st.error(action["message"])

    if action.get("logs"):
        with st.expander("查看运行日志", expanded=action["kind"] == "error"):
            st.code(action["logs"], language="text")


def _run_action(
    book_path: str,
    action: str,
    goal: str,
    prompt_preset_id: str,
    live_log_placeholder,
    *,
    chapter_count: int = 1,
) -> None:
    try:
        result = _run_live_action(
            live_log_placeholder,
            heading="正在执行工作流...",
            runner=lambda log_callback: run_book_action(
                book_path,
                action,
                main_story_goal=goal,
                chapter_count=chapter_count,
                prompt_preset_id=prompt_preset_id,
                log_callback=log_callback,
            ),
        )
    except Exception as exc:
        _set_last_action(
            kind="error",
            message=str(exc),
            logs=traceback.format_exc(),
        )
    else:
        _set_last_action_result(result)
    st.rerun()


def _run_live_action(live_log_placeholder, heading: str, runner):
    live_log_placeholder.empty()
    with live_log_placeholder.container():
        status = st.status(heading, expanded=True)
        log_box = st.empty()
        log_box.code("等待日志输出...", language="text")

        def on_log_update(logs: str) -> None:
            summary = _latest_log_summary(logs)
            status.update(label=summary or heading, state="running", expanded=True)
            log_box.code(_trim_logs(logs), language="text")

        result = runner(on_log_update)
        status.update(
            label=result.message,
            state="complete" if result.success else "error",
            expanded=not result.success,
        )
        if result.logs:
            log_box.code(_trim_logs(result.logs), language="text")
        else:
            log_box.code("没有日志输出。", language="text")
        return result


def _latest_log_summary(logs: str) -> str:
    for line in reversed(logs.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped[:160]
    return ""


def _trim_logs(logs: str, max_chars: int = 16000) -> str:
    if len(logs) <= max_chars:
        return logs
    return "... 日志过长，以下为最新输出 ...\n" + logs[-max_chars:]


def _set_last_action_result(result) -> None:
    _set_last_action(
        kind="success" if result.success else "error",
        message=result.message,
        logs=result.logs,
    )


def _set_last_action(*, kind: str, message: str, logs: str) -> None:
    st.session_state["last_action"] = {
        "kind": kind,
        "message": message,
        "logs": logs,
    }


def _default_book_index(paths: list[str]) -> int:
    selected_path = st.session_state.get("selected_book_path")
    if selected_path in paths:
        return paths.index(selected_path)
    return 0


def _default_prompt_preset_index(prompt_preset_ids: list[str]) -> int:
    return _safe_index(prompt_preset_ids, "default")


def _prompt_preset_label(prompt_preset_id: str, prompt_presets: list[dict[str, Any]]) -> str:
    for preset in prompt_presets:
        if preset["id"] == prompt_preset_id:
            return f"{preset['name']} ({preset['id']})"
    return prompt_preset_id


def _default_prompt_editor_index(prompt_preset_ids: list[str], book_view: dict | None) -> int:
    selected_preset_id = st.session_state.get("prompt-editor-preset-id")
    if selected_preset_id in prompt_preset_ids:
        return prompt_preset_ids.index(selected_preset_id)
    if book_view:
        book_prompt_preset_id = str(book_view.get("summary", {}).get("prompt_preset_id", "default"))
        if book_prompt_preset_id in prompt_preset_ids:
            return prompt_preset_ids.index(book_prompt_preset_id)
    return _default_prompt_preset_index(prompt_preset_ids)


def _format_template_name(template_name: str) -> str:
    return template_name.replace("_prompt", "").replace("_", " ").title()


def _format_prompt_field_name(field_name: str) -> str:
    return field_name.replace("_", " ").title()


def _safe_index(values: list[str], selected: str) -> int:
    if selected in values:
        return values.index(selected)
    return 0


if __name__ == "__main__":
    main()
