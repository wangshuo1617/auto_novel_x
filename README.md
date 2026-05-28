# Auto Novel X

全流程自动化 AI 网文创作系统。基于大语言模型，从世界观构建、人物设计到章节写作、质检与归档，实现一键生成多卷小说。

## 特性

- **五阶段流水线**：创世与战略 → 策划与编剧 → 质检与风控 → 数据回写与循环
- **多智能体协作**：世界架构师、元素设计师、分卷导演、情景工程师、正文塑造者、毒舌书评人、连贯性守门员、历史档案馆等
- **支持断点续写**：可从已有书籍目录继续创作，自动恢复世界观、卷计划、剧情弧与历史记录
- **每书独立数据库**：SQLite 存储角色、物品、地图等，便于单本书状态管理
- **Prompt 预设体系**：支持维护多套 agent prompt，并为每本书绑定独立的 prompt 预设

## 环境要求

- Python ≥ 3.12
- [uv](https://github.com/astral-sh/uv)（推荐）或 pip

## 快速开始

### 1. 克隆与安装

```bash
git clone <repo_url>
cd auto_novel_x
uv sync
```

### 2. 配置 API Key

在项目根目录创建 `.env` 文件：

```
GEMINI_API_KEY=your_gemini_api_key
```

本系统使用 **Google Gemini** 作为 LLM 后端。

### 3. 运行

**新建书籍：**

```python
from workflows.main_loop import MainLoop

main_loop = MainLoop(
    output_dir="output",
    trend_analysis={},  # 可选：市场趋势分析（见下方 TrendScout）
    human_idea="主角是一座庙，通过吸收香火来获得力量，苟道+非人器物视角+玄幻。",
    main_story_goal="成仙",
    prompt_preset_id="default",  # 可选：指定本书使用的 Prompt 预设
)
main_loop.run(max_chapters=10, max_volumes=1)
```

**从已有书籍继续：**

```python
main_loop = MainLoop(
    book_dir_path="output/book_20260130_215334",
    main_story_goal="成仙",  # 可更新全书目标
    prompt_preset_id="default",  # 可选；不传则优先读取 book_meta.json 中记录的预设
)
main_loop.run(max_chapters=20, max_volumes=2)
```

### 4. 启动前端控制台

```bash
streamlit run frontend/app.py
```

前端支持：

- 新建并初始化书籍
- 通过侧边栏顶部按钮打开 Prompt 编辑弹窗，新建多套 Prompt 预设，并编辑每个 agent 的 prompt / schema
- 新建书籍时选择 Prompt 预设，并在主区域的 Prompt 配置 tab 中为当前书籍切换绑定预设
- 生成下一章 / 手动开启新卷
- 阅读章节正文与对应 lore 档案
- 编辑 JSON / Markdown 产出物
- 按 SQLite 表查看、编辑、新增和删除角色/地点/物品等数据库记录
- 查看书籍健康检查、章节生成状态机记录和 LLM 调用日志

### 5. 以 systemd 后台运行前端

仓库内已提供：

- `scripts/run_frontend.sh`：前端启动脚本
- `systemd/auto-novel-x-frontend.service`：systemd unit

如果仓库路径不是 `/root/auto_novel_x`，请先修改 unit 文件中的 `User`、`WorkingDirectory` 和 `ExecStart`。

```bash
sudo cp systemd/auto-novel-x-frontend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now auto-novel-x-frontend
```

常用命令：

```bash
# 重启前端
sudo systemctl restart auto-novel-x-frontend

# 查看状态
sudo systemctl status auto-novel-x-frontend

# 查看日志
sudo journalctl -u auto-novel-x-frontend -f
```

**结合趋势侦察（可选）：**

```python
from agents import TrendScout
from workflows.main_loop import MainLoop

scout = TrendScout()
report = scout.run(
    platforms=["qidian"],
    rank_types=["monthly", "recommend", "new"],
    max_books=20,
    analysis_only=True,
)

main_loop = MainLoop(
    output_dir="output",
    trend_analysis=report,
    human_idea="主角是一座庙，通过吸收香火来获得力量，苟道+非人器物视角+玄幻。",
)
main_loop.run(max_chapters=10, max_volumes=1)
```

## 项目结构

```
auto_novel_x/
├── agents/                 # 智能体
│   ├── world_architect.py   # 世界架构师：构建世界观与商业分析
│   ├── element_designer.py  # 元素设计师：角色、物品、地图
│   ├── arc_director.py      # 分卷导演：卷规划与路线图
│   ├── plot_engineer.py     # 情景工程师：剧情大纲
│   ├── draft_smith.py       # 正文塑造者：章节正文
│   ├── simulated_reader.py  # 毒舌书评人：爽度审核
│   ├── continuity_keeper.py # 连贯性守门员：逻辑检查
│   ├── lore_archivist.py    # 历史档案馆：章节归档与摘要
│   ├── trend_scout.py       # 趋势侦察兵：排行榜爬取与题材分析
│   └── prompt/              # 各智能体的 prompt 模板
├── workflows/               # 工作流
│   ├── main_loop.py         # 主循环入口
│   ├── book_loader.py       # 已有书籍加载
│   ├── phase_initialization.py   # 阶段1：创世与战略
│   ├── chapter_pipeline.py # 阶段2–4：单章流水线
│   └── phase_new_volume.py  # 开新卷
├── prompt_presets/          # Prompt 预设（运行时自动生成默认预设，可在前端编辑）
├── utils/
│   ├── database.py          # 每书 SQLite 数据库
│   ├── consistency_checker.py # 书籍产物/数据库一致性检查
│   ├── generation_state.py  # 章节生成状态机记录
│   ├── llm_client.py        # Gemini 客户端
│   ├── llm_logging.py       # LLM 调用日志归档
│   └── prompt_presets.py    # Prompt 预设加载与运行时切换
├── memory/                  # 记忆与向量存储（预留）
├── config.py
├── pyproject.toml
└── README.md
```

## 创作流程

| 阶段 | 内容 |
|------|------|
| **1. 创世与战略** | 世界架构师生成世界观（含商业分析）→ 元素设计师创建初始角色/物品 → 分卷导演规划第一卷 |
| **2. 策划与编剧** | 情景工程师生成剧情大纲 → 正文塑造者撰写章节正文 |
| **3. 质检与风控** | 毒舌书评人审核爽度（不通过则重写大纲）→ 连贯性守门员检查逻辑（不通过则重写正文） |
| **4. 数据回写** | 历史档案馆归档 → 更新 `story_memory`、roadmap 完成标记、悬念 → 保存章节 Markdown |
| **5. 循环** | 当前卷 roadmap 阶段全部完成后由分卷导演规划新卷，继续下一章 |

## 输出格式

每本书对应一个目录（如 `output/book_20260130_215334/`），包含：

- `world_setting.json` / `world_setting.md`：世界观与商业分析
- `database.db`：SQLite 数据库（角色、地点、物品、状态、背包、关系等，前端直接从这里展示和编辑）
- `story_memory.json`：长期累计摘要、最近章节摘要、未完结线索、知识碎片与 roadmap 完成标记
- `volume_*_plan.json`：各卷计划
- `volume_001_plot_arc_ch001_ch010.json` …：按章节范围保存的剧情弧（每份通常覆盖 10 章）
- `volume_001_chapter_001.md` …：章节正文
- `volume_001_lore_record_ch001.json` …：各章历史档案
- `generation_state/` 与 `latest_generation_state.json`：章节生成状态机记录，用于失败排查与恢复判断
- `llm_runs/`：每次 agent 调用的 prompt、schema、响应、耗时与错误日志
- `book_meta.json`：前端记录的创意、全书目标、Prompt 预设等元信息

## Prompt 预设

- 所有 agent prompt 现在都通过 `prompt_presets/<preset_id>/` 加载。
- 系统首次访问时会自动把 `agents/prompt/` 中的当前模板落盘为 `default` 预设。
- 你可以在前端的 **Prompt 编辑** tab 中：
  - 克隆已有预设，生成新的风格化 prompt 套装
  - 编辑每个 agent 的 `system_prompt` / `user_prompt` / `json_schema`
  - 将某套预设绑定到当前书籍
- 每本书绑定的预设会记录在其 `book_meta.json` 中；后续继续生成时会自动沿用。

## 脚本

**重置书籍数据库：**

```bash
# 清空表数据
python scripts/reset_book_db.py output/book_20260130_215334

# 删除并重建数据库文件
python scripts/reset_book_db.py output/book_20260130_215334 --drop-file
```

## 依赖

- `google-genai`：Gemini API
- `langchain` / `langgraph`：链与图编排（预留）
- `chromadb`：向量存储（预留）
- `selenium` / `beautifulsoup4`：TrendScout 爬虫
- `streamlit`：预览/调试（预留）

详见 `pyproject.toml`。

## License

MIT
