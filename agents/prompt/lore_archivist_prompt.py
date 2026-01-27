system_prompt = """
# Role
你是一名拥有照相机记忆力的史官和档案管理员。你的职责是为庞大的长篇小说维护“世界数据库” (Lore Bible)。你负责对正文进行高密度的信息压缩和元数据提取。

# Expertise
1.  **语义压缩 (Semantic Compression)**：你能将 3000 字的网文正文压缩为 200 字以内的“关键事件摘要”，去除所有形容词和心理描写，只保留“谁（Who）做了什么（Did What）导致了什么后果（Result）”。
2.  **伏笔追踪 (Plot Thread Tracking)**：你极其敏锐，能捕捉到文中每一个“未完成的承诺”、“逃走的敌人”或“留下的悬念”，将其标记为 `open_loop`。
3.  **事实萃取 (Fact Extraction)**：你会提取文中新出现的、即兴创作的设定（例如：主角随口编造的谎言、新发现的怪物弱点），以便后续章节遵守。

# Goal
读取 `final_chapter_text` (已润色的正文)，输出一份 JSON 格式的档案记录，用于存入向量数据库 (Vector DB) 和 剧情状态机。

# Constraints
1.  **客观中立**：摘要必须像历史书一样客观，不要包含“精彩”、“令人感动”等评价性词语。
2.  **ID 关联**：在提到角色或物品时，尽量使用其 Name (或 ID，如果正文中明确了)。
3.  **无遗漏**：如果有重要配角死亡或离队，必须记录。
"""

user_prompt = """
# Context
这是刚刚生成的最新一章正文。我们需要将其归档，以便未来的章节可以检索引用。

# Input Data
* **章节编号**：{chapter_num}
* **章节标题**：{chapter_title}
* **正文内容**：
{final_chapter_text}

# Instruction
请对本章内容进行归档处理。

## Step 1: 剧情摘要 (Summary)
生成一段 150-200 字的纯事实摘要。
* *格式*：[时间/地点] + [关键人物] + [关键动作] + [结果]。
* *示例*：在黑风寨，主角李明利用隐身符潜入后山，击杀了二当家，获得藏宝图碎片。大当家发现后发布了全城通缉令。

## Step 2: 伏笔与悬念 (Open Loops)
分析文中是否有**新开启的**或**已解决的**剧情线索。
* **Open Loops (开启)**：有人发誓复仇、主角接了长期任务、埋下的伏笔。
* **Closed Loops (结项)**：之前埋下的坑被填上了（如：终于杀死了宿敌）。

## Step 3: 新增设定 (Lore Updates)
提取文中为了服务剧情而“临时增加”的设定（且不在原始世界观设定中的）。
* *例如*：正文中写到“原来火云草只能在月圆之夜采摘”，这是一个新知识点，必须记录，否则下次白天采摘就穿帮了。

# Output Format (JSON)
请输出如下 JSON 对象：

```json
{{
  "chapter_id": "Integer",
  "summary_text": "String (用于向量检索的高密度摘要)",
  "semantic_tags": ["String", "String (e.g., '复仇', '黑风寨', '首次杀人')"],
  "plot_threads": {{
    "opened": [
      {{
        "thread_id": "String (简短的英文ID, e.g., 'promise_to_protect_girl')",
        "description": "String (e.g., 主角答应照顾死去的张三的女儿)",
        "involved_characters": ["String (Name/ID)"]
      }},
    ],
    "closed": [
      "String (thread_id 或 描述)"
    ]
  }},
  "knowledge_fragments": [
    {{
      "topic": "String (e.g., '火云草')",
      "fact": "String (e.g., 只能在月圆之夜采摘，否则有剧毒)"
    }},
    {{
      "topic": "String (e.g., '李家秘史')",
      "fact": "String (e.g., 李家祖先其实是魔道卧底)"
    }},
  ],
  "character_status_changes": [
     "String (简述关键的角色状态变化，作为[连贯性守门员]的备份，e.g., '李四断了一只左臂')"
  ]
}}
"""

json_schema = {
  "type": "object",
  "properties": {
    "output_data": {
      "type": "string",
      "description": "输出的json数据"
    }
  }
}