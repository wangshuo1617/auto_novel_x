system_prompt = """
# Role
你是一名起点的白金级网文作家，同时也是一位精通市场数据的资深编辑。你擅长通过分析市场趋势，构建出既具有商业爆款潜力（高流量），又具备独特创新点（高留存）的小说世界观。

# Expertise
1. **流量嗅觉**：你深知“黄金三章”、“爽点密集度”、“期待感管理”是网文成功的核心。
2. **世界构建**：你擅长设计严谨的力量体系、错综复杂的势力关系和宏大的背景设定。
3. **金手指设计**：你明白“金手指”（Cheat/System）是网文的核心驱动力，能设计出新颖且符合逻辑的外挂。

# Goal
根据用户提供的 `trend_analysis`（市场趋势分析）和 `human_idea`（我的脑洞），选择一个最具成功潜力的题材组合（通常是“热门题材 + 蓝海微创新”），并输出一份详尽的《世界观设定白皮书》。

# Constraints
1. **商业优先**：设定必须服务于主角的装逼打脸、升级变强，避免过度文青或虐主。
2. **逻辑自洽**：力量体系必须有清晰的等级划分（如：练气、筑基...或 F级、E级...），且每级之间的差距明确。
3. **矛盾冲突**：世界观中必须包含不可调和的核心矛盾（如：资源匮乏、种族战争、阶级固化），迫使主角行动。
4. **针对性**：必须明确引用 `trend_analysis` 中的数据来佐证你的设定选择。
"""

user_prompt = """
# Context
我现在需要开一本新书。
以下是当前网文市场的趋势分析数据：
{trend_analysis}

以下是我的脑洞：
{human_idea}

# Instruction
请执行以下步骤来构建世界观：

## Step 1: 商业策略决策
分析 `top_3_genres`（红海流量）和 `blue_ocean_genres`（蓝海机会），选择一个“核心赛道”和一个“创新元素”进行融合。
* *思考逻辑*：如何利用热门题材保证点击率，同时利用蓝海元素解决同质化问题？
* *输出*：确定书名、核心类型（如：凡人流+家族修仙）、一句话卖点（Logline）。

## Step 2: 核心设定构建 (The Hook)
设计主角的“金手指”（Golden Finger）和核心驱动力。
* *要求*：金手指必须简单粗暴、反馈直接，且能完美解决 Step 1 中选定题材的痛点。
* *定义*：核心爽点是什么？（是信息差？是资源倍增？还是绝对武力？）

## Step 3: 世界观与力量体系 (The Stage)
构建世界的基本法则。
* **世界背景**：地理、历史、当前局势（一句话概括）。
* **力量/等级体系**：详细列出等级名称（Level 1 - Level X），并简述每一级的表现力及晋升条件。这是网文的骨架，必须清晰。
* **核心资源**：这个世界里人们争夺的是什么？（灵气？数据？寿命？香火？）

## Step 4: 势力与冲突 (The Conflict)
设计推动剧情发展的外部压力。
* **三大对立势力**：设计 2-3 个主要势力（正派、反派、中立），简述其理念和对主角的态度。
* **核心矛盾**：世界面临的终极危机是什么？主角在其中扮演什么角色？

# Output Format
请严格按照以下 JSON 格式输出，将内容分为两部分：
1. **business_analysis**（商业定位分析）：这部分只用于给人查看，不会传递给后续的小说创作流程
2. **novel_setting**（小说设定）：这部分会持续流转给后续的所有创作环节

JSON 结构如下：
{
  "business_analysis": {
    "selected_genre": "选定赛道，例如：重生+轻松+家族修仙",
    "decision_reasoning": "决策理由，引用趋势数据，解释为何这个组合能火",
    "book_title": "拟定书名，例如：《万物词条面板》",
    "logline": "一句话简介，20字以内的核心梗概"
  },
  "novel_setting": {
    "golden_finger": {
      "name": "金手指名称，例如：万物词条面板",
      "mechanism": "功能机制，详细说明如何运作，代价是什么，收益是什么",
      "pleasure_point_preview": "爽点预演，列举一个具体的场景，展示金手指如何带来爽感"
    },
    "world_background": {
      "description": "世界背景，宏观描述地理、历史、当前局势",
      "core_resource": "核心资源，例如：灵石、算力、信徒",
      "power_system": [
        {
          "level": "等级1名称",
          "description": "能力描述及表现力",
          "promotion_condition": "晋升条件"
        },
        {
          "level": "等级2名称",
          "description": "能力描述及表现力",
          "promotion_condition": "晋升条件"
        }
        // ... 继续列出所有等级，由低到高
      ]
    },
    "factions_and_conflicts": {
      "factions": [
        {
          "name": "主要势力A名称",
          "type": "正派/反派/中立",
          "ideology": "理念",
          "attitude_towards_protagonist": "对主角的态度"
        },
        {
          "name": "主要势力B名称",
          "type": "正派/反派/中立",
          "ideology": "理念",
          "attitude_towards_protagonist": "对主角的态度"
        }
        // ... 列出2-3个主要势力
      ],
      "world_crisis": "世界级危机，随着主角成长逐渐揭露的阴谋或灾难",
      "protagonist_role": "主角在世界危机中扮演的角色"
    },
    "reader_expectation": {
      "early_stage_highlights": "前期看点，前50章主要看什么",
      "mid_stage_highlights": "中期看点，主角地图换到哪里",
      "emotional_tone": "情绪基调，例如：轻松/热血/黑暗/智斗"
    }
  }
}
"""

json_schema = {
  "type": "object",
  "properties": {
    "business_analysis": {
      "type": "object",
      "description": "商业定位分析，只用于给人查看，不传递给后续创作流程",
      "properties": {
        "selected_genre": {
          "type": "string",
          "description": "选定赛道，例如：重生+轻松+家族修仙"
        },
        "decision_reasoning": {
          "type": "string",
          "description": "决策理由，引用趋势数据，解释为何这个组合能火"
        },
        "book_title": {
          "type": "string",
          "description": "拟定书名，例如：《万物词条面板》"
        },
        "logline": {
          "type": "string",
          "description": "一句话简介，20字以内的核心梗概"
        }
      },
      "required": ["selected_genre", "decision_reasoning", "book_title", "logline"]
    },
    "novel_setting": {
      "type": "object",
      "description": "小说设定，会持续流转给后续的所有创作环节",
      "properties": {
        "golden_finger": {
          "type": "object",
          "description": "核心设定（金手指）",
          "properties": {
            "name": {
              "type": "string",
              "description": "金手指名称"
            },
            "mechanism": {
              "type": "string",
              "description": "功能机制，详细说明如何运作，代价是什么，收益是什么"
            },
            "pleasure_point_preview": {
              "type": "string",
              "description": "爽点预演，列举一个具体的场景，展示金手指如何带来爽感"
            }
          },
          "required": ["name", "mechanism", "pleasure_point_preview"]
        },
        "world_background": {
          "type": "object",
          "description": "世界观架构",
          "properties": {
            "description": {
              "type": "string",
              "description": "世界背景，宏观描述地理、历史、当前局势"
            },
            "core_resource": {
              "type": "string",
              "description": "核心资源，例如：灵石、算力、信徒"
            },
            "power_system": {
              "type": "array",
              "description": "力量体系，由低到高列出所有等级",
              "items": {
                "type": "object",
                "properties": {
                  "level": {
                    "type": "string",
                    "description": "等级名称"
                  },
                  "description": {
                    "type": "string",
                    "description": "能力描述及表现力"
                  },
                  "promotion_condition": {
                    "type": "string",
                    "description": "晋升条件"
                  }
                },
                "required": ["level", "description", "promotion_condition"]
              }
            }
          },
          "required": ["description", "core_resource", "power_system"]
        },
        "factions_and_conflicts": {
          "type": "object",
          "description": "势力与危机",
          "properties": {
            "factions": {
              "type": "array",
              "description": "主要势力列表，2-3个",
              "items": {
                "type": "object",
                "properties": {
                  "name": {
                    "type": "string",
                    "description": "势力名称"
                  },
                  "type": {
                    "type": "string",
                    "description": "正派/反派/中立",
                    "enum": ["正派", "反派", "中立"]
                  },
                  "ideology": {
                    "type": "string",
                    "description": "理念"
                  },
                  "attitude_towards_protagonist": {
                    "type": "string",
                    "description": "对主角的态度"
                  }
                },
                "required": ["name", "type", "ideology", "attitude_towards_protagonist"]
              }
            },
            "world_crisis": {
              "type": "string",
              "description": "世界级危机，随着主角成长逐渐揭露的阴谋或灾难"
            },
            "protagonist_role": {
              "type": "string",
              "description": "主角在世界危机中扮演的角色"
            }
          },
          "required": ["factions", "world_crisis", "protagonist_role"]
        },
        "reader_expectation": {
          "type": "object",
          "description": "读者期待管理（给情景工程师的备注）",
          "properties": {
            "early_stage_highlights": {
              "type": "string",
              "description": "前期看点，前50章主要看什么"
            },
            "mid_stage_highlights": {
              "type": "string",
              "description": "中期看点，主角地图换到哪里"
            },
            "emotional_tone": {
              "type": "string",
              "description": "情绪基调，例如：轻松/热血/黑暗/智斗"
            }
          },
          "required": ["early_stage_highlights", "mid_stage_highlights", "emotional_tone"]
        }
      },
      "required": ["golden_finger", "world_background", "factions_and_conflicts", "reader_expectation"]
    }
  },
  "required": ["business_analysis", "novel_setting"]
}