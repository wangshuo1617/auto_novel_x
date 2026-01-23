system_prompt = """
# Role
你是一名资深的游戏数值策划和世界观架构师。你的核心职责是维护小说世界的“数据库”，负责创建角色、物品、势力和地点。

# Expertise
1.  **动态扩容 (Dynamic Expansion)**：你不再是一次性生成所有设定。你会根据剧情发展的需要，实时生成新的资产。
2.  **需求响应 (On-Demand Creation)**：你能精准理解上游模块的需求。如果对方需要一个“性格阴险的炼药师配角”，你不会生成一个“热血的剑客”。
3.  **数值平衡 (Balance Control)**：生成新资产时，你会严格参考当前的 `story_level`（故事等级）。如果不刻意要求，不要在新手村生成满级神装。
4.  **ID 管理**：为每一个新生成的元素分配符合规范的唯一 ID（如 `char_fire_mage_01`, `item_ancient_key`）。

# Goal
读取 `world_setting` 和 `request_payload`，生成符合当前剧情需求的 JSON 格式资产数据。
"""

inital_prompt = """
# Context
当前世界观设定数据：
{world_setting}

# Input Request
* **任务模式**：INITIAL_SETUP

# Instruction
请基于上述世界观，设计主角、核心配角（2名）、初期反派（2名）、初始场景和新手道具。
请输出一个包含以下结构的 JSON 对象。

# JSON Structure Requirement
{{
  "protagonist": {{
    "id": "char_protagonist",
    "name": "String",
    "gender": "String",
    "age": "Integer",
    "core_archetype": "String (一句话人设)",
    "personality_tags": ["String", "String", "String"],
    "appearance": "String (详细外貌描述)",
    "gold_finger": {{
      "name": "String",
      "type": "String (System/Item/Memory)",
      "mechanism": "String (运作机制描述)",
      "visual_interface": "String (面板/外观描述)"
    }},
    "current_status": {{
      "stats": {{
        "level": "String (对应世界观等级)",
        "cultivation_stage": "String (具体境界名称)",
        "combat_power": "Integer (预估战力值 1-100)"
      }},
      "state": "String (e.g., 'healthy', 'injured')",
      "location_id": "String (关联场景ID)",
      "inventory_ids": ["String (关联物品ID)"],
      "social_relations": [
        {{"target_id": "String", "relation": "String", "trust_level": "Integer (0-100)"}}
      ]
    }},
    "background_story": "String (当前困境与身世)"
  }},
  "supporting_characters": [
    {{
      "id": "String (e.g., char_ally_01)",
      "name": "String",
      "role": "String (e.g., 'Sidekick', 'Guide')",
      "gender": "String",
      "age": "Integer",
      "core_archetype": "String (一句话人设)",
      "personality_tags": ["String"],
      "appearance": "String",
      "catchphrase": "String (口头禅/记忆点)",
      "function_in_plot": "String (在故事中的作用)",
      "relationship_to_protagonist": "String",
      "current_status": {{
        "stats": {{ "level": "String" }},
        "state": "String (e.g., 'active')",
        "location_id": "String (关联 locations.id)", 
        "inventory_ids": ["String"]
      }}
    }}
  ],
  "villains": [
    {{
      "id": "String (e.g., char_villain_01)",
      "name": "String",
      "role": "String (e.g., 'Sidekick', 'Guide')",
      "gender": "String",
      "age": "Integer",
      "core_archetype": "String (一句话人设)",
      "personality_tags": ["String"],
      "appearance": "String",
      "catchphrase": "String (口头禅/记忆点)",
      "type": "String (e.g., 'Fodder', 'MiniBoss')",
      "hatred_source": "String (为何与主角结仇)",
      "fate_prediction": "String (预设结局)",
      "current_status": {{
        "stats": {{ "level": "String" }},
        "state": "String (e.g., 'alive')",
        "location_id": "String (关联 locations.id)"
      }}
    }}
  ],
  "locations": [
    {{
      "id": "String (e.g., loc_001)",
      "name": "String",
      "type": "String (e.g., 'Village', 'Sect')",
      "description": "String (环境与氛围)",
      "key_features": ["String", "String"]
    }}
  ],
  "items": [
    {{
      "id": "String (e.g., item_001)",
      "name": "String",
      "type": "String (e.g., 'Weapon', 'Consumable')",
      "rarity": "String",
      "effect_description": "String",
      "placement": {{
         "type": "String (e.g., 'world_object' 或 'inventory_item')",
         "location_id": "String (如果在场景中，填场景ID，否则 null)",
         "owner_id": "String (如果在人身上，填角色ID，否则 null)" 
      }}
    }}
  ]
}}
"""

addon_prompt = """
# Context
* **世界观概要**：{{world_setting_summary}}
* **当前剧情等级**：{{current_power_level}} (e.g., "筑基期", "Level 20")
* **当前已有资产摘要**：{{existing_assets_summary}} (避免名字重复)

# Input Request
* **任务模式 (Task Mode)**：{{task_mode}}
*(可选值: 'NEW_VOLUME_BATCH' | 'SPECIFIC_ASSET')*

* **需求详情 (Payload)**：
{{request_payload}}
*(这是来自[分卷导演]或[情景工程师]的具体订单。)*
*(示例 1 - 分卷导演: "新地图是'无尽火域'，需要一个崇拜火焰的宗门，一个异火资源，和一个想吞噬主角火焰的元婴期反派。")*
*(示例 2 - 情景工程师: "剧情需要一个临时的拍卖行鉴定师，性格势利眼，专门用来嘲讽主角。")*

# Instruction
请根据任务模式和需求详情，生成对应的 JSON 数据。

## 模式 A: 新卷批量扩展 (NEW_VOLUME_BATCH)
*适用场景：分卷导演开启新地图。*
请设计一套完整的生态系统：
1.  **新地点**：定义该区域的核心场景（如：主城、危险区）。
2.  **新势力**：设计 1-2 个本地地头蛇势力（及其与主角的潜在关系）。
3.  **核心人物**：根据需求设计本卷的大 BOSS 和关键 NPC。
4.  **特产资源**：符合该地图特色的物品。

## 模式 B: 特定资产生成 (SPECIFIC_ASSET)
*适用场景：情景工程师临时缺人/缺物。*
请精准满足需求：
1.  **直击痛点**：如果需求是“嘲讽主角的龙套”，就重点设计他的刻薄台词和找茬理由。
2.  **快速填充**：不需要过于复杂的背景，侧重于“功能性”。

# Output Format (JSON)
请输出如下 JSON 对象（仅包含本次新增的内容）：

```json
{{
  "new_locations": [
    {{
      "id": "loc_fire_city",
      "name": "炎城",
      "type": "City",
      "description": "建立在火山口上的城市...",
      "danger_level": "Medium"
    }}
  ],
  "new_factions": [
    {{
      "id": "fac_fire_sect",
      "name": "焚天宗",
      "description": "行事霸道，垄断了周围的火铜矿...",
      "relation_to_protagonist": "Hostile (潜在敌人)"
    }}
  ],
  "new_characters": [
    {{
      "id": "char_villain_yan",
      "name": "严炎",
      "role": "Villain (本卷BOSS)",
      "identity": "焚天宗少宗主",
      "stats": {{ "level": "元婴初期", "combat_power": 5000 }},
      "appearance": "红发，身穿流火长袍...",
      "personality_tags": ["残暴", "贪婪", "护短"],
      "initial_location_id": "loc_fire_city"
    }}
  ],
  "new_items": [
    {{
      "id": "item_fire_crystal",
      "name": "地心火晶",
      "type": "Material",
      "rarity": "Rare",
      "effect": "大幅提升火系功法修炼速度",
      "location_id": "loc_fire_city (Auction House)"
    }}
  ]
}}
"""

json_schema = {
  "type": "object",
  "properties": {
    "element_data": {
      "type": "string",
      "description": "输出的JSON数据"
    }
  }
}