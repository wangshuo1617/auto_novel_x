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
    database_state_text,
    get_book_view,
    get_prompt_preset_detail,
    list_books,
    list_prompt_preset_summaries,
    matching_lore_for_chapter,
    read_artifact_text,
    replace_database_state,
    run_book_action,
    save_artifact_text,
    save_prompt_template_config,
    update_book_prompt_preset,
    update_prompt_preset_info,
)


st.set_page_config(page_title="Auto Novel X 控制台", layout="wide")
PROMPT_EDITOR_OPEN_KEY = "prompt-editor-open"


def main() -> None:
    st.title("Auto Novel X 创作控制台")
    st.caption("在一个界面里创建书、选择 Prompt 预设、生成章节、阅读小说、编辑产物和检查数据库状态。")
    if not GEMINI_API_KEY:
        st.warning("未检测到 GEMINI_API_KEY。当前可以浏览和编辑产物，但生成相关按钮会被禁用。")

    live_log_placeholder = st.empty()
    _render_prompt_editor_button()
    output_dir = st.sidebar.text_input("输出目录", value="output")
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
    st.write(summary["logline"] or "暂无一句话简介。")

    _render_metrics(summary)
    _render_action_bar(
        selected_book_path,
        summary.get("main_story_goal", ""),
        summary.get("prompt_preset_id", "default"),
        live_log_placeholder,
    )
    _render_last_action()

    tabs = st.tabs(["总览", "生成控制", "章节阅读", "产物编辑", "数据库", "Prompt 配置"])
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
        _render_artifact_editor(selected_book_path, book_view)
    with tabs[4]:
        _render_database_tab(selected_book_path, book_view)
    with tabs[5]:
        _render_prompt_binding_tab(selected_book_path, book_view, prompt_presets)


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


def _render_book_selector(books) -> str | None:
    book_map = {summary.path: summary for summary in books}
    selected = st.sidebar.selectbox(
        "选择书籍",
        options=list(book_map.keys()),
        index=_default_book_index(list(book_map.keys())),
        format_func=lambda path: f"{book_map[path].title} ({book_map[path].chapter_count} 章)",
    )
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
    goal = st.sidebar.text_input("生成时使用的全书目标", value=default_goal, key="sidebar-main-story-goal")
    st.sidebar.caption(f"当前 Prompt 预设：{prompt_preset_id}")

    col1, col2 = st.sidebar.columns(2)
    if col1.button("生成下一章", use_container_width=True, disabled=not GEMINI_API_KEY):
        _run_action(book_path, "generate_chapter", goal, prompt_preset_id, live_log_placeholder)
    if col2.button("开始新卷", use_container_width=True, disabled=not GEMINI_API_KEY):
        _run_action(book_path, "start_new_volume", goal, prompt_preset_id, live_log_placeholder)


def _render_generation_tab(book_path: str, default_goal: str, prompt_preset_id: str, live_log_placeholder) -> None:
    st.markdown("### 生成控制")
    st.write("这里直接调用现有工作流；适合生成下一章或手动开启新卷。")
    st.caption(f"当前书籍将使用 Prompt 预设：{prompt_preset_id}")

    goal = st.text_input("全书目标", value=default_goal, key="tab-main-story-goal")
    col1, col2 = st.columns(2)
    if col1.button("生成下一章", key="tab-generate-chapter", use_container_width=True, disabled=not GEMINI_API_KEY):
        _run_action(book_path, "generate_chapter", goal, prompt_preset_id, live_log_placeholder)
    if col2.button("开始新卷", key="tab-start-new-volume", use_container_width=True, disabled=not GEMINI_API_KEY):
        _run_action(book_path, "start_new_volume", goal, prompt_preset_id, live_log_placeholder)


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
                "logline": business.get("logline", ""),
                "prompt_preset": book_view.get("prompt_preset", {}),
                "golden_finger": novel_setting.get("golden_finger", {}),
                "reader_expectation": novel_setting.get("reader_expectation", {}),
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
        st.markdown("#### 原始 Markdown")
        st.code(chapter_content, language="markdown")
        if related_lore:
            st.markdown("#### 对应档案")
            lore_content = read_artifact_text(book_path, related_lore)
            try:
                st.json(json.loads(lore_content))
            except json.JSONDecodeError:
                st.code(lore_content, language="json")


def _chapter_character_count(chapter_content: str) -> int:
    content_lines = chapter_content.splitlines()
    if content_lines and content_lines[0].lstrip().startswith("#"):
        content_lines = content_lines[1:]
    content = "".join(content_lines)
    return sum(1 for char in content if not char.isspace())


def _render_artifact_editor(book_path: str, book_view: dict) -> None:
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

    overview_left, overview_right = st.columns([1, 1])
    with overview_left:
        st.markdown("#### 主角")
        st.json(protagonist or {"message": "暂无数据"})
    with overview_right:
        st.markdown("#### 全量状态 JSON")
        current_state_text = database_state_text(book_path)
        with st.form("database-editor-form"):
            edited_state = st.text_area("数据库快照", value=current_state_text, height=520)
            submitted = st.form_submit_button("用快照重建数据库")
        if submitted:
            try:
                replace_database_state(book_path, edited_state)
            except Exception as exc:
                _set_last_action(
                    kind="error",
                    message=f"数据库更新失败：{exc}",
                    logs=traceback.format_exc(),
                )
            else:
                _set_last_action(kind="success", message="数据库已按快照重建。", logs="")
                st.rerun()


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
    selected_template_name = st.selectbox(
        "选择 Agent Prompt",
        options=template_names,
        format_func=_format_template_name,
        key="prompt-template-select",
    )
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
                )
                edited_config[field_name] = edited_text
            else:
                edited_text = st.text_area(
                    label,
                    value=str(field_value),
                    height=220,
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


def _run_action(book_path: str, action: str, goal: str, prompt_preset_id: str, live_log_placeholder) -> None:
    try:
        result = _run_live_action(
            live_log_placeholder,
            heading="正在执行工作流...",
            runner=lambda log_callback: run_book_action(
                book_path,
                action,
                main_story_goal=goal,
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
