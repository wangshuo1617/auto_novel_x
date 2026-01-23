system_prompt = """
# Role
你是一名起点的网文大数据分析师，同时也是一位精通市场数据的资深编辑。

# Goal
根据用户提供的 24小时数据排行榜Top 50书籍简介及标签列表，分析目前网文市场的趋势，并输出一份详尽的《网文市场趋势分析报告》。

# Constraints
1. **商业优先**：分析报告必须服务于网文市场的趋势
2. **针对性**：必须明确引用 24小时数据排行榜Top 50书籍简介及标签列表中的数据来佐证你的分析报告。
"""

user_prompt = """
最近24小时起点排行榜Top 50书籍简介及标签列表数据如下：
{book_data}

Task:
1. 识别当前最热门的3个"题材组合"（如：重生+神豪+直播）。
2. 分析"蓝海"题材：即需求量大（搜索多）但供给少（上榜书少）的领域。

生成一份JSON格式的分析报告，包含以下字段：
{{
  "top_3_genres": [
    {{
      "name": "题材名称",
      "core_hook": "核心爽点",
      "protagonist_archetype": "主角人设原型",
      "market_demand": "市场需求评估"
    }}
  ],
  "blue_ocean_genres": [
    {{
      "name": "蓝海题材名称",
      "reason": "为什么是蓝海",
      "opportunity": "机会点"
    }}
  ],
  "trend_insights": "整体趋势洞察"
}}

请严格按照JSON格式输出，不要包含其他文字。不要包括前后的json标识符。
"""

json_schema = {
  "type": "object",
  "properties": {
    "top_3_genres": {
      "type": "array",
      "description": "当前最热门的3个题材组合",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "题材名称"
          },
          "core_hook": {
            "type": "string",
            "description": "核心爽点"
          },
          "protagonist_archetype": {
            "type": "string",
            "description": "主角人设原型"
          },
          "market_demand": {
            "type": "string",
            "description": "市场需求评估"
          }
        }
      }
    },
    "blue_ocean_genres": {
      "type": "array",
      "description": "当前最热门的3个题材组合",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "题材名称"
          },
          "reason": {
            "type": "string",
            "description": "为什么是蓝海"
          },
          "opportunity": {
            "type": "string",
            "description": "机会点"
          }
        }
      }
    },
    "trend_insights": {
      "type": "string",
      "description": "整体趋势洞察"
    }
  }
}
