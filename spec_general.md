

# **通用叙事系统设计：构建跨题材的世界观与成长引擎**

## **执行摘要**

从专用的“修仙”世界观生成器向通用叙事引擎的转型，代表了系统设计领域的一次根本性范式转移——即从硬编码的内容建模向抽象的结构建模的跨越。虽然修仙题材依赖于特定的层级（如炼气至金丹）和特定的资源循环（如灵石），但通过深入分析，我们发现这些仅仅是**成长阶梯（Progression Tiers）**、\*\*资源经济（Resource Economies）**和**组织拓扑（Organizational Topologies）\*\*的具体实例化。为了实现真正的通用性，必须将这些底层机制抽象为元数据结构。

本报告详细阐述了一个通用的世界观与设计生成器的架构方案，该方案不仅能够支持修仙题材，还能无缝适配科幻、都市异能、悬疑推理、末世生存以及西幻史诗等多种题材。通过利用图数据库本体论、JSON Schema 验证机制以及动态的大语言模型（LLM）提示工程，我们能够构建一个模块化系统，其中“题材”仅仅是覆盖在通用核心之上的配置层。本分析借鉴了 GURPS（通用角色扮演系统）的设计原则、Neo4j 知识图谱建模技术以及先进的上下文工程策略，旨在提供一份详尽的、可落地执行的一万五千字技术蓝图。

---

## **1\. 本体论抽象：从“宗门”到“组织实体”的语义解构**

实现世界观系统通用化的首要任务，是对特定题材术语进行语义上的解构与重构。在修仙系统中，社会结构的基本单元是“宗门”，核心能量是“灵气”。而在赛博朋克设定中，这些概念分别对应“巨型企业”和“电力/资本”。若要构建通用本体，必须超越表层的名词差异，转而关注实体的**功能性**而非**风味性**。

### **1.1 元实体架构与超节点设计**

通用生成器的基础数据结构必须依赖抽象的实体类型。知识图谱建模的研究表明，实体的定义应基于其关系和属性，而非静态标签 1。我们建议采用一种“超节点（Hypernode）”架构，其中特定的题材标签仅作为通用节点类型的属性存在 3。这种设计允许系统在不同语境下动态解析实体的具体表现形式，从而实现真正的跨题材兼容性。

#### **1.1.1 组织拓扑的同构性分析**

在修仙题材中，宗门拥有严格的层级结构（外门弟子 \-\> 内门弟子 \-\> 长老）。在企业科幻设定中，这直接映射为职级阶梯（实习生 \-\> 初级专员 \-\> 执行高管）。通用模型采用\*\*基于职级的层级图（Rank-Based Hierarchical Graph）\*\*来统一这些结构。通过分析不同题材的组织结构，我们发现其内在逻辑具有惊人的同构性。

| 通用属性 | 修仙题材映射 | 赛博朋克映射 | 末世生存映射 | 悬疑/黑帮映射 | 西幻史诗映射 |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **组织单元** | 宗门 / 家族 | 巨型企业 / 财团 | 幸存者营地 / 避难所 | 警局 / 犯罪家族 | 公会 / 骑士团 |
| **层级 1 (入门)** | 外门弟子 / 杂役 | 外包工 / 零工 | 拾荒者 / 难民 | 菜鸟警察 / 街头混混 | 学徒 / 见习侍从 |
| **层级 2 (核心)** | 内门弟子 | 正式员工 / 专员 | 守卫 / 种植者 | 探员 / 打手 | 正式法师 / 骑士 |
| **层级 3 (精英)** | 真传弟子 / 护法 | 中层管理 / 部门主管 | 议会成员 / 队长 | 警督 / 副手 | 导师 / 圣骑士 |
| **层级 4 (领袖)** | 太上长老 / 宗主 | 董事会 / CEO | 军阀 / 领主 | 局长 / 教父 | 大法师 / 团长 |
| **核心资源** | 灵石 / 丹药 | 信用点 / 数据 | 食物 / 燃料 / 弹药 | 情报 / 人情 / 赃款 | 金币 / 魔力水晶 |
| **控制领地** | 灵脉 / 洞天福地 | 生态建筑 / 服务器群 | 地下掩体 / 安全区 | 辖区 / 地盘 | 城堡 / 魔法塔 |

**深度洞察：** “宗门”与“公司”在结构上的同构性意味着我们可以使用相同的图遍历算法来生成冲突。一场争夺“灵脉”的“宗门战争”，在机制上与一场争夺“数据中心”的“恶意收购”，或者一场争夺“地盘”的“帮派火拼”是完全等价的 4。生成器只需保留**动词逻辑**（冲突、获取、防御），并在渲染阶段替换**名词标签**即可。这种抽象不仅减少了代码冗余，还为跨题材混合（如“赛博修仙”）提供了天然的兼容性基础。

此外，这种拓扑结构还揭示了组织内部的权力动态。在任何层级系统中，晋升往往伴随着资源的重新分配和权限的扩大。通用系统可以通过定义“晋升条件”（如贡献度、实力阈值、特殊任务）来自动化生成角色的成长路径。例如，修仙者的“大比”与公司员工的“绩效考核”在系统层面均可视为一种“晋升事件”，其触发条件和结果反馈遵循同一套逻辑模板。

### **1.2 资源经济模型的抽象化**

在通用RPG设计原则中，经济系统往往是驱动冲突的核心引擎。无论是“金币”、“信用点”还是“卡路里”，其底层的数学模型都是关于稀缺性与积累的博弈 6。一个健壮的通用系统必须能够模拟不同类型的资源流动，并将其与角色的成长挂钩。

通用JSON Schema 对资源的定义必须包含以下维度：

1. **获取向量（Acquisition Vector）：** 资源如何被引入系统？（例如：通过采矿、战斗掉落、贸易交换、调查取证）。  
2. **衰减率（Decay Rate）：** 资源是否会随时间贬值或消失？（末世中的食物会腐烂，而奇幻中的黄金通常保值）。  
3. **转化效率（Conversion Efficiency）：** 资源转化为实力的路径和损耗。（例如：经验曲线的斜率、装备购买的性价比）。  
4. **流动性（Liquidity）：** 资源在不同实体间转移的难易程度。（货币的高流动性 vs 绑定装备的零流动性）。

代码片段：通用资源定义 Schema 8

JSON

{  
  "$schema": "http://json-schema.org/draft-07/schema\#",  
  "title": "UniversalResource",  
  "type": "object",  
  "description": "定义任何可被收集、消耗或交易的叙事资产",  
  "properties": {  
    "resourceId": { "type": "string", "pattern": "^\[a-z0-9\_\]+$" },  
    "genreLabel": { "type": "string", "description": "在特定题材下的显示名称，如'灵石'或'比特币'" },  
    "scarcityLevel": {   
      "type": "integer",   
      "minimum": 1,   
      "maximum": 10,  
      "description": "1为泛滥，10为极其稀有/唯一"  
    },  
    "isTangible": { "type": "boolean", "description": "是否为实体物品" },  
    "primaryFunction": {  
      "type": "string",  
      "enum":  
    },  
    "exchangeRate": {  
      "type": "number",  
      "description": "相对于基准经济单位的价值"  
    },  
    "decayProfile": {  
      "type": "object",  
      "properties": {  
        "hasDecay": { "type": "boolean" },  
        "decayRate": { "type": "number", "description": "每单位时间的损耗百分比" }  
      }  
    }  
  },  
  "required": \["resourceId", "genreLabel", "primaryFunction"\]  
}

通过利用这一Schema，生成器可以实例化“法力水晶”（实体、能量、稀缺度5、无衰减）或“内部情报”（非实体、信息、稀缺度8、高衰减），并确保两者在系统内部的处理逻辑是一致的。例如，系统可以生成一个“资源危机”事件，无论是“法力枯竭”还是“情报过时”，其对主角造成的紧迫感和行动驱动力在叙事结构上是相似的。

**第二阶洞察：** 资源的属性直接决定了叙事的节奏。高衰减率的资源（如末世中的食物）会迫使主角进行频繁、短期的冒险（Scavenging Runs）；而低衰减、高价值的资源（如修仙中的修为）则鼓励长期的规划和闭关（Cultivation）。通用生成器可以通过调整资源的decayRate和scarcityLevel参数，自动调节生成故事的“生存压力”与“长期目标”之间的平衡。

---

## **2\. 抽象成长引擎：量化力量与晋升逻辑**

“修仙境界”（炼气、筑基等）仅仅是\*\*分层成长系统（Tiered Progression System）\*\*的一个特例。为了支持通用设定，我们必须采用类似于 GURPS 或 Hero System 的模型，将力量视为可以通过点数或抽象层级来量化的指标，而非依赖于特定的叙事头衔 6。

### **2.1 通用力量量表 (Universal Power Scale, UPS)**

我们定义一个 0-10 的标准化量表，用于跨题材归一化战斗力与影响力。这使得系统能够平衡一个法师与一个赛博格，或者一个侦探与一场政治丑闻的威胁等级。这种标准化的核心在于确立“相对威胁”而非“绝对物理数值”。

| UPS 层级 | 描述与定义 | 奇幻/修仙表现 | 科幻/超能表现 | 悬疑/凡人表现 | 影响范围 |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **0** | **凡俗 / 弱势** | 凡人、农夫 | 未改造人类、平民 | 受害者、路人 | 个人 |
| **1-2** | **受训 / 职业** | 城市卫兵、学徒 | 士兵、街头武士 | 巡警、记者 | 街道/小队 |
| **3-4** | **精英 / 超凡** | 骑士队长、筑基修士 | 特种部队、重型赛博格 | 资深探员、连环杀手 | 街区/建筑 |
| **5-6** | **城市威胁 / 战术级** | 大法师、金丹老祖 | 机甲驾驶员、AI核心 | 幕后黑手、犯罪集团 | 城市/战役 |
| **7-8** | **大陆威胁 / 战略级** | 半神、元婴/化神 | 轨道轰炸、纳米瘟疫 | (N/A \- 题材天花板) | 大陆/国家 |
| **9-10** | **宇宙 / 概念级** | 真神、大乘/飞升 | 戴森球文明、高维生物 | (N/A \- 题材天花板) | 星球/位面 |

**深度洞察：** “题材天花板（Genre Ceiling）”是一个至关重要的配置变量。悬疑小说通常在 Tier 3（制度性权力）或 Tier 4（极少数高智商罪犯）封顶，而修仙小说则必须一路延伸至 Tier 10。生成器必须在初始化阶段强制执行这些上限，以防止基调失调。如果一个“黑色侦探”故事的主角突然获得了 Tier 7 的破坏力，整个叙事的逻辑基础（依赖法律、证据和逻辑）将瞬间崩塌 10。因此，UPS 不仅是数值参考，更是叙事边界的执法者。

此外，不同层级之间的跨越难度（Delta Difficulty）也是可配置的。在修仙题材中，Tier 3 打败 Tier 4 几乎是不可能的（阶级压制），但在科幻题材中，Tier 2 的黑客可能通过技术手段瘫痪 Tier 5 的AI系统（弱点攻击）。通用引擎需要引入“克制系数”或“非对称对抗机制”来模拟这些差异。

### **2.2 技能树与科技树：有向无环图 (DAG) 的统一**

在修仙中，成长通常是线性的或基于“道”的分支。在科幻和RPG中，成长则被建模为技能或科技的**有向无环图 (DAG)** 11。为了实现通用化，系统应将所有形式的进步视为 DAG 中的\*\*节点解锁（Node Unlocking）\*\*过程。

* **魔法系统：** 节点是法术（Spells）。边是前置的奥术知识或特定的法力阈值。  
* **科技系统：** 节点是蓝图（Blueprints）或植入体（Implants）。边是研究点数或稀有材料。  
* **技能系统：** 节点是能力（Abilities）。边是经验值或训练时间。

通用成长结构 JSON 示例 12：

JSON

{  
  "progressionTree": {  
    "treeId": "combat\_mastery",  
    "rootNodeId": "basic\_training",  
    "nodes":,  
        "effects": \[  
          { "target": "self", "attribute": "mana", "change": \-10 },  
          { "target": "enemy", "attribute": "hp", "change": \-50 }  
        \],  
        "narrativeTag": "destructive"  
      },  
      {  
        "id": "tech\_shield\_gen\_01",  
        "label": "{{genre\_term\_defense\_tech}}",  
        "nodeType": "PassiveUpgrade",  
        "cost": { "type": "credits", "value": 1500 },  
        "requirements": \["basic\_training"\],  
        "effects": \[  
          { "target": "self", "attribute": "shield", "change": \+20 }  
        \],  
        "narrativeTag": "protective"  
      }  
    \]  
  }  
}

通过使用 **Jinja2** 模板语法（如 {{ }}），genre\_term\_attack\_spell 变量可以在运行时被替换为“火球术”（奇幻）或“等离子射击”（科幻）14。更重要的是，DAG 结构允许复杂的依赖关系，如“必须先掌握《基础内功》（节点A）和《人体经络图》（节点B），才能解锁《易筋经》（节点C）”，这种逻辑在科技树中同样适用（先研究“激光物理”和“高能电池”，才能解锁“激光步枪”）。

### **2.3 魔法与科技的本质区别：“仪式”与“工厂”**

在构建通用系统时，最大的挑战之一是如何区分魔法与科技的**质感（Feel）**。如果仅仅是数值上的差异，两者会变得同质化。研究表明，核心区别在于**可复制性（Reproducibility）和个性化（Personalization）** 16。

* **科技（量产逻辑）：** 物品是标准化的，力量是外在的（枪在射击，而不是人）。提升来自于**获取**更好的硬件。科技的力量通常是可预期的、稳定的，且不依赖使用者的精神状态。  
* **魔法（仪式/艺术逻辑）：** 效果因施法者而异，力量是内在的。提升来自于**理解**、**顿悟**或**练习**。魔法往往带有不可预测性、个人风格，且难以大规模复制。

**系统设计启示：**

* 对于**科幻/科技设定**，生成器应生成庞大的*掉落表（Loot Tables）和商店库存*，其中包含标准化的、分级的高科技物品（如“马克IV型等离子步枪”）。玩家的成长曲线呈阶梯状，随着装备更新而跳跃。  
* 对于**魔法/修仙设定**，生成器应生成*秘籍（Manuals）*、*导师（Teachers）和顿悟事件（Insight Events）*，这些机制直接修改角色的内部属性。玩家的成长曲线更平滑，但受到“瓶颈”机制的限制。

**第三阶洞察：** 这种区分不仅仅是机制上的，它影响了世界观的社会结构。科技主导的世界倾向于资本主义或集权主义（因为生产资料集中）；魔法主导的世界倾向于精英主义或师徒制（因为知识传递依赖个人指导）。通用生成器应根据选择的“力量来源类型”自动调整生成的社会背景描述，从而增强世界观的内在一致性。

---

## **3\. 跨题材叙事架构：结构化的故事引擎**

生成器必须超越特定的情节桥段（如修仙中的“打脸”），转向通用的叙事结构。我们整合了经典的叙事理论——特别是\*\*丹·哈蒙的故事环（Story Circle）**和**救猫咪（Save the Cat）\*\*节拍表，作为事件生成的骨架 18。

### **3.1 通用情节循环模型**

大多数成长型小说（包括LitRPG、修仙、少年漫）都遵循一个递归的\*\*冲突-解决-奖励（Conflict-Resolution-Reward）\*\*循环 21。

1. **需求状态（State of Need）：** 主角需要资源 X 以晋升下一层级。  
2. **激励事件（Inciting Incident / Hook）：** 获得资源 X 的机会出现（任务、副本、比赛、案件）。  
3. **冲突展开（Conflict）：** 对手或环境阻碍主角获取资源。  
4. **危机与高潮（Crisis & Climax）：** 必须做出抉择或超越极限。  
5. **解决（Resolution）：** 成功获取或失败（付出代价）。  
6. **奖励/后果（Reward/Consequence）：** 实力提升（或下降/受伤）。  
7. **新状态（New State）：** 主角现在需要资源 Y（Tier \+ 1）。

图数据库实现：  
在 Neo4j 中，这被建模为事件链（Event Chain）。  
(:Character) \--\> (:Resource) \<-- (:Antagonist)  
(:Event) \--\> (:Conflict)  
(:Event) \--\> (:Resource)  
这种图结构允许系统查询“谁阻碍了主角获取当前急需的资源”，并据此生成针对性的反派和挑战。

### **3.2 模块化的题材节拍表 (Genre Modules)**

虽然循环是通用的，但节拍的**风味（Flavor）和侧重点**随题材而变。我们可以创建“题材模块”，将特定的类型片桥段映射到标准节拍结构上。

#### **3.2.1 模块 A：悬疑/黑色电影节拍**

22

* **钩子（Hook）：** “黄金三章”原则——必须是秩序的破坏。尸体被发现，或者神秘客户上门。  
* **中点（Midpoint）：** “伪胜利/伪失败”——侦探抓住了嫌疑人，但发现抓错了；或者意识到阴谋远比想象中深。  
* **高潮（Climax）：** 首先是智力上的对抗（揭穿诡计），紧接着是物理上的解决（追捕/枪战）。  
* **关键变量：** 成长指标是信息（Information/Clues），而非简单的XP。每一个线索的获得都推动剧情向真相逼近。

#### **3.2.2 模块 B：末世生存节拍**

24

* **钩子（Hook）：** 安全感的丧失。避难所被攻破，或者关键物资（水/药）耗尽。  
* **中点（Midpoint）：** 发现“避风港”，但随后揭示其阴暗面（如独裁军阀、食人族、瘟疫隐患）。  
* **高潮（Climax）：** 保卫新家园或逃离死亡陷阱。  
* **关键变量：** 物资（Supplies）和信任（Trust）。物资的消耗是恒定的时间压力（Ticking Clock），信任的建立与背叛是核心戏剧冲突。

#### **3.2.3 模块 C：赛博朋克/科幻节拍**

4

* **钩子（Hook）：** “差事（The Job）”。中间人发布针对大公司的任务。  
* **中点（Midpoint）：** 背叛。雇主为了灭口而出卖团队，或者队友是卧底。  
* **高潮（Climax）：** “突围（The Run）”。潜入黑点或带着数据杀出重围。  
* **关键变量：** 信用点（Credits）和街头声望（Street Cred）。声望决定了能接到什么级别的任务，金钱决定了能购买什么级别的装备。

### **3.3 动态节奏控制算法**

网络小说对节奏的要求与传统出版小说截然不同。特别是“黄金三章”法则，要求在前 6,000 字内完成钩子、冲突和奖励的闭环 23。通用引擎需要内置**节奏监控器**。

**事件生成算法伪代码：**

Python

def generate\_event(current\_pacing\_score, genre\_config, word\_count):  
    \# 黄金三章逻辑检查  
    if word\_count \< 6000 and not story\_state.has\_hook:  
        return genre\_config.get\_event("catalyst", high\_stakes=True)

    if current\_pacing\_score \< threshold:  
        \# 节奏过慢，注入高冲突事件  
        \# 赛博朋克：战斗/追逐；悬疑：新的尸体/袭击侦探  
        return genre\_config.get\_event("conflict\_escalation")   
    else:  
        \# 节奏过快，允许休整/消化奖励  
        \# 赛博朋克：修车/交易；悬疑：验尸/访谈  
        return genre\_config.get\_event("recovery\_consolidation")

**深入分析：** 这种算法确保了故事不会陷入“流水账”或“无限高潮”的极端。在修仙小说中，“休整”往往是“闭关修炼”或“炼丹”，这是将战斗收益转化为实力的关键步骤。在悬疑小说中，“休整”是整理线索、推理分析的过程，是将零散信息转化为逻辑链条的关键。系统必须识别出不同题材下“低节奏”环节的功能性差异。

---

## **4\. 技术实现：通用引擎的架构蓝图**

为了实现上述设计，我们建议采用基于 **JSON Schema** 的数据定义和 **LLM Prompt Engineering** 的内容生成相结合的技术栈。

### **4.1 配置驱动的架构 (Configuration-Driven Architecture)**

系统不应硬编码规则，而应在运行时加载 题材配置对象 (Genre Configuration Object)。这使得添加新题材只需编写新的 JSON 文件，无需修改代码逻辑。

示例题材配置（赛博朋克）8：

JSON

{  
  "genre\_id": "cyberpunk\_01",  
  "meta\_tags": \["sci-fi", "dystopian", "high-tech", "low-life"\],  
  "terminology": {  
    "energy": "Battery/Power",  
    "currency": "Euro-Dollars (eddies)",  
    "organization": "Mega-Corp",  
    "skill\_provider": "Ripperdoc",  
    "power\_unit": "Cyberware Capacity"  
  },  
  "world\_physics": {  
    "magic\_exists": false,  
    "tech\_level": "High",  
    "scarcity\_driver": "Artificial/Capitalist",  
    "law\_enforcement": "Privatized"  
  },  
  "narrative\_templates": \["heist", "corporate\_war", "street\_survival", "ai\_rogue"\],  
  "trope\_mappings": {  
    "sect\_elder": "Board\_Member",  
    "spirit\_beast": "Combat\_Drone",  
    "secret\_realm": "Offline\_Server\_Vault",  
    "enlightenment": "Data\_Download"  
  },  
  "ups\_scaling": {  
    "max\_tier": 8,  
    "tier\_names":  
  }  
}

### **4.2 基于 Jinja2 的动态提示工程**

使用 **Jinja2** 模板引擎允许我们编写单一的“主提示词（Master Prompt）”，该提示词能够根据选定的题材配置在运行时动态适应 14。这种方法将逻辑结构与文本生成解耦。

**主提示词模板示例：**

代码段

你是一位专精于 {{ genre\_config.meta\_tags|join(', ') }} 题材的小说生成专家。  
当前主角处于 {{ genre\_config.ups\_scaling.tier\_names\[current\_tier\] }} 阶段（Tier {{ current\_tier }}）。

当前目标：获取 {{ genre\_config.terminology.currency }} 以升级/购买 {{ genre\_config.terminology.power\_unit }}。  
主要反派：一个名为 "{{ antagonist\_name }}" 的 {{ genre\_config.terminology.organization }}。

任务：生成一个剧情节拍，主角面临一个典型的 {{ genre\_config.narrative\_templates|random }} 场景。  
约束条件：  
1\. 冲突必须围绕 {{ genre\_config.terminology.energy }} 的稀缺性展开。  
2\. 使用 {{ genre\_config.terminology.skill\_provider }} 作为提升能力的途径。  
3\. 风格指南：{{ genre\_config.style\_guide }}。  
4\. 请勿出现魔法或超自然描述，除非物理规则允许。

上下文注入策略：  
为了保证生成的一致性，必须将“世界状态”注入到 LLM 的上下文窗口中。我们不传入整部小说，而是传入“知识图谱”的压缩 JSON 摘要（包含活跃关系、当前位置属性、关键NPC状态）26。这种\*\*检索增强生成（RAG）\*\*策略确保了即使在长篇连载中，AI 也不会忘记主角的人际关系或已获得的物品。

### **4.3 图数据库 Schema 设计 (Neo4j)**

通用图 Schema 避免使用具体的标签如 Cultivator 或 Jedi，而是使用通用标签。

**节点定义：**

* Agent (角色, AI, 怪物)  
* Group (派系, 队伍, 公司, 宗门)  
* Location (场景, 星球, 房间, 秘境)  
* Object (物品, 麦格芬, 资源)  
* Concept (技能, 秘密, 法律, 知识)

**关系定义：**

* OWNS / CONTROLS (控制权)  
* ANTAGONISTIC\_TO / ALLIED\_WITH (社交关系)  
* LOCATED\_IN (空间关系)  
* KNOWS / MASTERED (知识/技能掌握)  
* REQUIRES / PROVIDES (前置条件/奖励)

这种 Schema 允许复杂的通用查询，例如：“查找所有与主角敌对的 Agent，这些 Agent 控制着一个拥有高密度目标 Resource 的 Location”。这个查询在奇幻中可能返回“黑龙占据了金矿”，在科幻中可能返回“流氓AI控制了聚变反应堆” 1。

---

## **5\. 案例研究：通用引擎的应用验证**

为了证明该架构的通用性，我们将展示同一套底层逻辑如何生成三种截然不同的题材体验。

### **5.1 场景 A：“宗门大比”原型的变体**

* **通用结构：**  
  * **事件：** 竞争性选拔流程。  
  * **目标：** 获得更高的地位/权限/资源。  
  * **约束：** 基于表现的淘汰制。  
  * **反派：** 竞争对手/宿敌。  
* **题材：修仙 (Cultivation)**  
  * *输出：* “外门大比。弟子们在擂台上对决，胜者晋升内门，获得筑基丹。”  
* **题材：赛博朋克 (Cyberpunk)**  
  * *输出：* “黑客马拉松（The Hackathon）。网络行者在虚拟空间攻防，胜者获得荒坂公司的外包合同及军用级ICE。”  
* **题材：末世生存 (Post-Apocalyptic)**  
  * *输出：* “雷霆穹顶（The Thunderdome）。幸存者在死斗笼中搏杀，胜者获得一油罐车的汽油和军阀议会的席位。”

**洞察：** 结构（图拓扑）是完全一致的。变化仅在于表皮（Jinja2 变量）。这证明了“竞争晋升”是一个普适的人类叙事原型。

### **5.2 场景 B：“秘境探险”原型的变体**

* **通用结构：**  
  * **事件：** 探索隔离的、高风险、高回报区域。  
  * **目标：** 回收古代/遗失的技术或魔法。  
  * **约束：** 时间限制或环境敌意。  
* **题材：悬疑/克苏鲁 (Mystery/Lovecraftian)**  
  * *输出：* “调查废弃庄园。侦探必须在星辰对齐前找到邪教的《死灵之书》。‘理智值（Sanity）’是衰减资源。”  
* **题材：硬科幻 (Hard Sci-Fi)**  
  * *输出：* “打捞废弃无畏舰。陆战队必须在维生系统失效前回收AI核心。‘氧气（Oxygen）’是衰减资源。”

---

## **6\. 实施建议与未来展望**

基于上述分析，我们提出以下具体实施建议：

1. **采用“基于组件（Component-Based）”的实体系统：** 摒弃硬编码的“法师”或“战士”类，转而创建由标签组成的实体（如 , \`\[Magic\_User\]\`, ）。这允许系统无需修改代码即可支持混合题材（如《暗影狂奔》式的赛博奇幻）。  
2. **分离模拟与叙述：** **模拟引擎**（处理资源数值、层级晋升、冲突结果）应是纯数学和 JSON 驱动的。**叙述引擎**（LLM）仅负责将这些数字解释为散文。绝对不要让 LLM 处理数学运算，因为它不仅不可靠，而且难以调试 29。  
3. **引入 JSON 规则引擎：** 使用如 json-rules-engine 的库将题材逻辑外部化。这允许用户通过简单的 JSON 文件上传来“Mod”系统，例如通过修改配置文件即可将系统从“武侠”变为“星际大战”，使系统具有真正的社区扩展性 30。  
4. **开发“跨题材融合”模块：** 未来的迭代应支持异构规则的碰撞。例如，处理“穿越”场景，当一个 Tier 10 的修仙者掉入一个 Tier 0 的赛博朋克世界时，系统应能计算“灵力”与“电力”的交互规则。

## **结论**

从修仙专用生成器向通用叙事引擎的演进，本质上并非抛弃“修仙”逻辑，而是对其进行**升维抽象**。修仙体系中严格的等级制实际上是所有类型小说中“从零到英雄（Zero-to-Hero）”成长曲线的最显性表达。通过采用图数据库本体论、变量驱动的提示工程以及模块化的配置架构，我们构建了一个数学骨架，它可以支撑起任何题材的血肉。这种设计赋予了用户极大的自由度——早晨生成道祖的飞升之路，晚上生成赛博侦探的雨夜追凶，而这一切都运行在同一套优雅、健壮的代码核心之上。

---

# **第一部分：通用本体论（数据层）**

## **1.1 解构题材特异性：从具体到抽象**

将“修仙”世界观生成器转化为通用系统的最大障碍，在于机制与风味的语义耦合。在原始设计中，Sect（宗门）可能是一个硬编码的类，包含 sect\_master（宗主）、spirit\_vein\_density（灵脉浓度）和 scripture\_library（藏经阁）等属性。这种设计紧密绑定了特定文化背景。在通用系统中，这些独特的元素必须被视为更广泛类别的实例。

为了实现通用性，我们必须执行**本体扁平化（Ontological Flattening）**。这意味着识别实体在叙事模拟中的功能角色，并剥离其题材特定的命名法 1。

### **1.1.1 “组织（Organization）”元类**

在几乎所有的RPG和成长叙事中，主角都会与控制资源和领地的等级制群体互动。

**通用组织 Schema 设计：**

* **核心功能：** 资源积累、成员保护、意识形态执行、领地扩张。  
* **资源来源：** 组织控制的主要资产（灵脉、股市、油田、魔法节点）。  
* **层级类型：**  
  * *精英制（Meritocratic）：* 企业、学院（凭能力晋升）。  
  * *血统制（Bloodline）：* 家族、封建领主（凭血缘晋升）。  
  * *力量制（Strength-based）：* 宗门、军阀、兽群（凭战斗力晋升）。

**表 1：组织的本体论映射**

| 叙事功能 | 修仙 (Xiuxian) | 赛博朋克 / 科幻 | 末世生存 | 都市奇幻 / 悬疑 |
| :---- | :---- | :---- | :---- | :---- |
| **主要实体** | 宗门 (Sect) | 巨型企业 (MegaCorp) | 定居点 / 营地 | 帮派 / 结社 |
| **领袖节点** | 老祖 / 宗主 | CEO / 董事长 | 军阀 / 镇长 | 教父 / 大祭司 |
| **精英单元** | 真传弟子 | 特勤组 / 高管 | 卫队 / 掠夺者 | 干部 / 杀手 |
| **劳工单元** | 外门弟子 | 社畜 / 劳工 | 拾荒者 | 马仔 / 苦力 |
| **资产 (源头)** | 灵脉 | 数据中心 / 专利 | 水源 / 军火库 | 毒品线 / 圣遗物 |
| **冲突模式** | 宗门战 (法术) | 收购战 / 商业间谍 | 掠夺 / 围攻 | 地盘争夺 / 调查 |

**实施洞察：** 在图数据库（Neo4j）中，我们定义一个节点标签 :Organization。该组织的*类型*是一个属性 genre\_type: "MegaCorp"。生成器的“冲突事件”逻辑保持不变：Organization A 试图夺取 Organization B 的 Asset。**叙事层**随后根据 genre\_type 属性，将“夺取资产”翻译为“攻打山门”或“黑入主机” 28。这种设计允许我们编写一次逻辑代码，复用于无限的题材场景。

### **1.1.2 “代理人（Agent）”元类（角色）**

虚构作品中的角色是变革的功能性代理人。通用 Schema 需要将“灵根”或“义体”等属性抽象为通用的 Capacity（能力）系统。

**通用角色数据模型 (JSON Schema)：**

JSON

{  
  "agent\_id": "uuid\_12345",  
  "name": "Protagonist",  
  "archetype": "{{genre\_archetype}}",   
  "attributes": {  
    "physical": 50,  // 力量, 体质, 硬件强度  
    "mental": 70,    // 智力, 感知, 算力, 神识  
    "social": 30     // 魅力, 声望, 面子, 信用评级  
  },  
  "progression": {  
    "tier": 2,       // 归一化的 0-10 量表  
    "tier\_label": "{{genre\_tier\_name}}", // 例如："筑基期" 或 "中层管理"  
    "accumulated\_resource": 1500  
  },  
  "relationships":  
}

* **自适应修正：** 我们必须避免硬编码如 Strength 或 Dexterity 这样的具体属性。如果题材是“社交惊悚片”，物理属性可能完全无关紧要。attributes 对象应根据题材配置动态填充 9。例如，在《唐顿庄园》风格的设定中，Social 可能细分为 Etiquette（礼仪）和 Lineage（血统）。

## **1.2 资源经济模型的抽象化**

经济驱动了绝大多数成长故事中的冲突。“灵石”经济是一个闭环系统：开采灵石 \-\> 吸收以增强力量 \-\> 力量允许开采更高阶的灵石。这种循环存在于所有题材中。

### **1.2.1 通用资源分类法**

我们将资源分为三个通用类别，以便于生成逻辑处理：

1. **流动资产 (Currency)：** 高交换性，战斗/实用效用低。（黄金、信用点、灵石、瓶盖）。  
2. **消耗品 (Consumable Utility)：** 一次性使用，即时效果。（丹药、弹药、医疗包、电池、魔法卷轴）。  
3. **永久资产 (Permanent Assets)：** 耐用，提供被动/主动属性加成。（法宝、义体、武器、证据文件、房产）。

**表 2：按题材分类的资源分类学**

| 类别 | 修仙 | 科幻 | 悬疑 | 末世 |
| :---- | :---- | :---- | :---- | :---- |
| **货币** | 灵石 | 信用点 / 加密货币 | 人情 / 现金 | 以物易物 (子弹) |
| **消耗品** | 丹药 | 能量电池 / 兴奋剂 | 咖啡 / 香烟 | 罐头 / 药品 |
| **永久资产** | 飞剑 | 植入体 / 动力甲 | 线索 / 档案 | 武器 / 改装车 |
| **抽象资产** | 道 / 顿悟 | 数据 / 访问权限 | 秘密 / 真相 | 希望 / 士气 |

**洞察：** 在悬疑小说中，Information（信息）的功能完全等同于 XP（经验值）。收集足够的线索（XP）允许侦探破案（升级/突破）。系统可以将“推理”建模为“修炼突破”事件，其中分散的 Clue 节点被合并为一个 Truth 节点，进而解锁剧情的下一阶段 23。

---

# **第二部分：抽象成长引擎（机制层）**

## **2.1 归一化力量量表 (0-10)**

通用系统的主要痛点在于“战力崩坏”或“量级不匹配”。修仙小说拥有指数级的力量曲线（神可以毁灭星球），而悬疑小说拥有线性曲线（侦探仅比菜鸟聪明一点）。

为了解决这个问题，我们实施一个**归一化对数量表（Normalized Logarithmic Scale）**，即 Tier 0-10。生成器计算冲突结果是基于**相对层级差（Relative Tier Delta）**，而非绝对数值。

* **Delta \+0 (同级):** 势均力敌 (50% 胜率)。  
* **Delta \+1:** 苦战 (20-30% 胜率，通常需要策略或外部辅助)。  
* **Delta \+2:** Boss 战 / 绝境 (5-10% 胜率，通常需要主角光环或特殊道具)。  
* **Delta \+3:** 不可战胜 / 仅能逃跑 (0% 胜率)。

题材缩放配置 (Scaling Configuration)：  
系统通过定义 MAX\_TIER 和 TIER\_SCOPE 来限制生成范围。

* *修仙:* Tier 10 \= 宇宙毁灭级。TIER\_SCOPE \= COSMIC。  
* *赛博朋克:* Tier 10 \= 全球控制 / AI 奇点。TIER\_SCOPE \= GLOBAL。  
* *丧尸末世:* Tier 10 \= 坚固城邦的领袖（物理力量依然是人类范畴）。TIER\_SCOPE \= REGIONAL。

通过定义 MAX\_TIER，系统知道在“丧尸生存”故事中不要生成“摧毁星球”的事件 7。

## **2.2 技能树与科技树作为有向无环图 (DAG)**

成长“树”是一个通用概念。无论是解锁“金丹期”还是研究“核聚变”，其逻辑都是：前置条件 \-\> 成本 \-\> 解锁 \-\> 效果。

### **2.2.1 统一节点结构**

我们使用 JSON 格式的 DAG 来表示所有形式的进步 12。

JSON

{  
  "node\_id": "tech\_plasma\_rifle",  
  "display\_name": "等离子武器技术",  
  "genre\_tags": \["combat", "ranged", "energy"\],  
  "prerequisites": \["tech\_laser\_rifle", "resource\_fusion\_battery"\],  
  "cost": {  
    "resource\_type": "research\_points",  
    "amount": 500  
  },  
  "unlock\_effect": {  
    "type": "add\_item\_to\_shop",  
    "item\_id": "weapon\_plasma\_mk1"  
  }  
}

**适应性说明：**

* 在**魔法**设定中，unlock\_effect 可能是 "grant\_spell: fireball"。  
* 在**LitRPG**设定中，unlock\_effect 可能是 "stat\_boost: \+10 INT"。  
* 在**悬疑**设定中，unlock\_effect 可能是 "unlock\_location: police\_archives"（解锁警察局档案室的访问权）。

### **2.2.2 “内求 vs 外求”切换开关**

系统需要区分**内在修炼**（魔法/武术/异能）和**外在获取**（科技/装备）。这不仅仅是设定问题，更影响了“战利品”逻辑。

* **内在路径 (Internal Path \- Magic/Cultivation):** 成长绑定在 *Agent* 身上。如果 Agent 死亡，力量通常会消失（除非有“夺舍”或“吞噬”机制）。  
  * *系统逻辑:* Agent.stats \+= Upgrade。  
* **外在路径 (External Path \- Tech/Gear):** 成长绑定在 *Inventory*（库存）上。如果 Agent 死亡，杀手可以捡走力量（枪支、机甲）。  
  * *系统逻辑:* Agent.inventory.add(Item)。

**深度洞察：** 这种区别根本上改变了“冲突奖励”逻辑。在修仙小说中，杀死敌人通常只获得储物袋（资源），很少直接获得力量。而在赛博朋克或末世小说中，“杀人越货”是获取高阶装备的主要手段（杀死穿动力甲的敌人 \-\> 获得动力甲）。生成器必须根据此开关调整“战利品生成（Loot Generation）”算法，以符合题材的内在逻辑 16。

---

# **第三部分：跨题材情节架构（叙事层）**

## **3.1 结构模板：从哈蒙环到救猫咪**

叙事结构为生成器提供了骨架。我们将两种主导模型整合，分别映射到网络小说的“无限连载”格式和传统小说的“封闭循环”格式。

### **3.1.1 递归的故事环 (Web Novel Mode)**

网络小说（以及 LitRPG、修仙、少年漫）本质上是一系列嵌套的**丹·哈蒙故事环 (Dan Harmon's Story Circles)** 18。

1. **你 (舒适区):** 主角处于当前的层级/位置。  
2. **需求 (欲望):** 需要资源以晋升下一层级（瓶颈期）。  
3. **出发 (跨越门槛):** 进入副本/秘境/案件现场。  
4. **搜索 (试炼):** 清理小怪/寻找线索。  
5. **发现 (遇袭):** 遭遇 Boss 或发现核心麦格芬。  
6. **获取 (代价):** 击败 Boss，获得战利品/顿悟，通常伴随受伤或损失。  
7. **回归 (变化):** 回到基地，消化战利品。  
8. **改变 (升级):** 达到下一层级，开启新的循环。

通用情节生成提示模板：  
系统通过迭代这8个步骤来生成情节。

* *步骤 2 (需求) 生成逻辑:* “查询图谱中 Agent 的 next\_required\_resource。查找包含此资源的 Location，且 difficulty \= Agent.Tier \+ 1。”

### **3.1.2 “黄金三章”法则 (The Golden Three Chapters)**

对于网络小说，开篇节奏至关重要。系统必须在开篇强制执行高密度的事件 23。

* **第一章：钩子 / 不公 (The Hook / Injustice)。**  
  * *修仙:* 退婚、废柴流、家族霸凌。  
  * *科幻:* 被公司无理解雇、背负巨额债务。  
  * *悬疑:* 离奇的尸体发现、被诬陷。  
* **第二章：金手指 / 催化剂 (The Golden Finger / Catalyst)。**  
  * *修仙:* 戒指老爷爷苏醒、系统激活。  
  * *科幻:* 捡到原型机芯片、觉醒异能。  
  * *悬疑:* 发现别人忽略的关键线索、获得神秘线人的电话。  
* **第三章：首次冲突 / 打脸 (First Conflict / Face Slapping)。**  
  * 立即验证新获得的力量，提供即时满足感。

## **3.2 动态冲突生成**

冲突是通过**Agent 目标**与**对抗力量**的交集生成的。

### **3.2.1 对抗性图遍历 (Antagonistic Graph Traversal)**

使用 Neo4j，我们可以通过路径查找来生成冲突 34。

* **查询语句:** MATCH (p:Protagonist), (a:Antagonist), (r:Resource) WHERE (p)--\>(r) AND (a)--\>(r) RETURN p, a, r  
* **叙事输出:** “主角需要，但它被 \[Antagonist\] 控制。”

**题材变体:**

* *奇幻:* “玩家需要 \[冰莲\]，但它由 \[冰霜巨龙\] 守护。”  
* *赛博朋克:* “玩家需要 \[原型芯片\]，但它被锁在 \[荒坂金库\] 中。”  
* *言情:* “玩家需要 \[好感度/认可\]，但被 \[误会/情敌\] 阻碍。”

---

# **第四部分：AI 集成与动态生成（提示层）**

## **4.1 Jinja2 模板用于上下文注入**

我们使用 Jinja2 创建“填空游戏（Mad Libs）”式的提示词，让 LLM 填充富有创造力的散文。这确保了*结构*遵循我们的设计，而*文笔*符合题材 14。

**“场景生成器”模板：**

Python

prompt\_template \= """  
题材语境: {{ genre\_description }}  
基调: {{ tone }} (例如：坚毅、希望、克苏鲁式恐怖)

当前场景设置:  
\- 主角: {{ protagonist.name }} (层级 {{ protagonist.tier }})  
\- 地点: {{ location.name }} ({{ location.environment\_tags }})  
\- 目标: {{ objective }}  
\- 障碍: {{ obstacle.name }} ({{ obstacle.type }})

任务: 撰写一个约 1000 字的场景。  
结构要求:  
1\. 使用符合 {{ genre }} 的感官细节建立场景。  
2\. 主角试图 {{ objective }} 但被 {{ obstacle.name }} 打断。  
3\. 爆发一场涉及 {{ combat\_system\_flavor }} 的冲突。  
4\. 以一个与 {{ mystery\_hook }} 相关的悬念结尾。  
"""

### **4.2 通过少样本提示 (Few-Shot Prompting) 实现风格迁移**

为了确保输出的“味道”正确（例如，“道家术语” vs “硬科幻技术术语”），我们将**少样本示例**注入到系统提示词中 36。

* **修仙配置:** 注入 3 个关于“冥想描述”、“武技喊话”和“天地异象”的例子。  
* **黑色电影配置:** 注入 3 个关于“内心独白”、“愤世嫉俗的比喻”和“雨夜描写”的例子。

算法:  
当用户选择题材时，系统加载该题材的 style\_examples.json 并将其追加到 LLM 的 system\_prompt 中。这种方法比微调模型更灵活，且成本更低。

## **4.3 处理“系统” (LitRPG 元素)**

许多现代网文会调用一个字面意义上的“游戏系统”。我们的通用引擎通过将“系统”视为模拟数据的**UI 包装器**来处理这一点。

* *如果 LitRPG Mode \= ON:* 生成器会在文本中显式输出蓝色方框 / 属性面板。  
  * *输出:* \[系统提示：你造成了 50 点暴击伤害！\]  
* *如果 LitRPG Mode \= OFF:* 生成器定性地描述属性。  
  * *输出:* “他感到一股爆发性的力量涌过肌肉，这一击势大力沉，足以开山裂石。”（代替了“力量+10”）。

---

# **第五部分：案例研究——架构实战**

## **5.1 案例研究：末世生存生成器**

**配置:**

* **题材:** 末世 (丧尸/核战)。  
* **资源:** 卡路里, 弹药, 药品。  
* **成长:** 基地建设 (科技树) \+ 拾荒 (探索)。  
* **组织:** 帮派, 幸存者定居点。

**生成循环演示:**

1. **需求:** 定居点缺乏 抗生素（治疗关键NPC）。  
2. **图查询:** 查找包含标签 \[Medical\] 且 \[Unexplored\] 的最近 Location。 \-\> 结果: "废弃的仁慈医院"。  
3. **冲突:** 地点拥有 Threat\_Level: 4。主角是 Tier: 2。 \-\> 系统判定为“高风险任务”。  
4. **叙事生成:** AI 生成一个“潜行/惊悚”风格的剧情节拍。修仙中的“守关神兽”角色由“变异憎恶”扮演，守卫着药房。  
5. **奖励:** 获得 抗生素 (资源) 和 旧世界数据硬盘 (成长道具/剧情物品)。

## **5.2 案例研究：企业赛博朋克生成器**

**配置:**

* **题材:** 赛博朋克。  
* **资源:** 信用点, 情报。  
* **成长:** 义体植入 (基于金钱)。  
* **组织:** 巨型企业。

**生成循环演示:**

1. **需求:** 主角需要 50,000 欧金购买 斯安威斯坦植入体（提升战斗速度）。  
2. **图查询:** 查找奖励 \> 50k 的 Job。 \-\> 结果: "从 BioTechnica 撤离 VIP"。  
3. **冲突:** VIP 被 公司安保 (Tier 3\) 看守。  
4. **叙事生成:** AI 生成一个“抢劫/突袭”风格的剧情节拍。“秘境”变成了“研发实验室”。  
5. **奖励:** 金钱 (货币) 和 公司黑料 (剧情物品/勒索素材)。

---

# **结论**

从修仙专用生成器到通用叙事引擎的跨越，并非通过创建一个无所不包的单一系统来实现，而是通过创建一个能够编排专业模块的**元系统 (Meta-System)**。通过将“修仙”抽象为“成长”，将“宗门”抽象为“层级组织”，将“灵气”抽象为“资源”，我们构建了一个可以支撑任何表皮的数学骨架。

结合**图数据库**（处理关系逻辑）、**JSON Schema**（定义实体）和**Jinja2 模板化的 LLM 提示词**（生成散文），我们实现了一个真正的通用设计。这个系统赋予了用户极大的灵活性——早晨生成道祖的飞升之路，晚上生成赛博侦探的雨夜追凶，而这一切都运行在完全相同的底层代码库之上，仅需切换配置文件。

未来工作:  
本研究的下一步是开发“跨题材融合”模块，使系统能够处理“无限流”或“综漫”场景，例如当一个 Tier 10 的修仙者穿越到一个 Tier 0 的赛博朋克世界时，系统能够动态计算“灵力”与“电力”的交互规则，测试系统处理上下文冲突的鲁棒性。

#### **引用的著作**

1. Ontologies in Neo4j: Semantics and Knowledge Graphs, 访问时间为 十一月 25, 2025， [https://neo4j.com/blog/knowledge-graph/ontologies-in-neo4j-semantics-and-knowledge-graphs/](https://neo4j.com/blog/knowledge-graph/ontologies-in-neo4j-semantics-and-knowledge-graphs/)  
2. Choosing A Graph Data Model to Best Serve Your Use Case \- Ontotext, 访问时间为 十一月 25, 2025， [https://www.ontotext.com/blog/choosing-a-graph-data-model-to-best-serve-your-use-case/](https://www.ontotext.com/blog/choosing-a-graph-data-model-to-best-serve-your-use-case/)  
3. GRAD: On Graph Database Modeling \- arXiv, 访问时间为 十一月 25, 2025， [https://arxiv.org/pdf/1602.00503](https://arxiv.org/pdf/1602.00503)  
4. 68 Sci-Fi Tropes You're Gonna Want to Know About \- Dabble, 访问时间为 十一月 25, 2025， [https://www.dabblewriter.com/articles/sci-fi-tropes](https://www.dabblewriter.com/articles/sci-fi-tropes)  
5. The rise of MEGA-CORPORATIONS in science fiction \- YouTube, 访问时间为 十一月 25, 2025， [https://www.youtube.com/watch?v=VtAGfvm6MOQ](https://www.youtube.com/watch?v=VtAGfvm6MOQ)  
6. Universal RPG Systems Compared (2025 Guide) | Manx Gaming Solutions, 访问时间为 十一月 25, 2025， [http://www.manxgamingsolutions.com/universal-rpg-systems.html](http://www.manxgamingsolutions.com/universal-rpg-systems.html)  
7. Choose Your Power Level \- Roleplay Rescue's Blog, 访问时间为 十一月 25, 2025， [https://roleplayrescue.com/2020/04/26/choose-your-power-level/](https://roleplayrescue.com/2020/04/26/choose-your-power-level/)  
8. Is it possible to write a generic JSON Schema? \- Stack Overflow, 访问时间为 十一月 25, 2025， [https://stackoverflow.com/questions/36985970/is-it-possible-to-write-a-generic-json-schema](https://stackoverflow.com/questions/36985970/is-it-possible-to-write-a-generic-json-schema)  
9. Hierarchical data structures \- JSON | CloverDX Tech Blog, 访问时间为 十一月 25, 2025， [https://www.cloverdx.com/tech-blog/hierarchical-data-json](https://www.cloverdx.com/tech-blog/hierarchical-data-json)  
10. Need help choosing a generic universal role playing system... that isn't GURPS : r/rpg, 访问时间为 十一月 25, 2025， [https://www.reddit.com/r/rpg/comments/w7xmv3/need\_help\_choosing\_a\_generic\_universal\_role/](https://www.reddit.com/r/rpg/comments/w7xmv3/need_help_choosing_a_generic_universal_role/)  
11. Free Skill Tree Maker | Skill Tree Templates \- Creately, 访问时间为 十一月 25, 2025， [https://creately.com/lp/skill-tree-maker/](https://creately.com/lp/skill-tree-maker/)  
12. JSON Tree – Xojo Programming Blog, 访问时间为 十一月 25, 2025， [https://blog.xojo.com/2019/03/11/json-tree/](https://blog.xojo.com/2019/03/11/json-tree/)  
13. Create a tree-like json object from an array of objects \- Stack Overflow, 访问时间为 十一月 25, 2025， [https://stackoverflow.com/questions/49998275/create-a-tree-like-json-object-from-an-array-of-objects](https://stackoverflow.com/questions/49998275/create-a-tree-like-json-object-from-an-array-of-objects)  
14. Prompt Templates with Jinja2 \- PromptLayer Blog, 访问时间为 十一月 25, 2025， [https://blog.promptlayer.com/prompt-templates-with-jinja2-2/](https://blog.promptlayer.com/prompt-templates-with-jinja2-2/)  
15. Jinja2 prompting — A guide on using jinja2 templates for prompt management in GenAI applications | by Alex Gonzalez | Medium, 访问时间为 十一月 25, 2025， [https://medium.com/@alecgg27895/jinja2-prompting-a-guide-on-using-jinja2-templates-for-prompt-management-in-genai-applications-e36e5c1243cf](https://medium.com/@alecgg27895/jinja2-prompting-a-guide-on-using-jinja2-templates-for-prompt-management-in-genai-applications-e36e5c1243cf)  
16. How to make Technology and Magic 'feel' different from each other? : r/RPGdesign \- Reddit, 访问时间为 十一月 25, 2025， [https://www.reddit.com/r/RPGdesign/comments/mq3zu3/how\_to\_make\_technology\_and\_magic\_feel\_different/](https://www.reddit.com/r/RPGdesign/comments/mq3zu3/how_to_make_technology_and_magic_feel_different/)  
17. Worlds of Design: Magic vs. Technology | EN World D\&D & Tabletop RPG News & Reviews, 访问时间为 十一月 25, 2025， [https://www.enworld.org/threads/worlds-of-design-magic-vs-technology.676916/](https://www.enworld.org/threads/worlds-of-design-magic-vs-technology.676916/)  
18. Dan Harmon Story Circle: The 8-Step Storytelling Shortcut \- Reedsy, 访问时间为 十一月 25, 2025， [https://reedsy.com/blog/guide/story-structure/dan-harmon-story-circle/](https://reedsy.com/blog/guide/story-structure/dan-harmon-story-circle/)  
19. Storytelling Guide: Dan Harmon's Story Circle Method Explained \- StudioBinder, 访问时间为 十一月 25, 2025， [https://www.studiobinder.com/blog/dan-harmon-story-circle/](https://www.studiobinder.com/blog/dan-harmon-story-circle/)  
20. How to Write Your Novel Using the Save the Cat Beat Sheet \- Jessica Brody, 访问时间为 十一月 25, 2025， [https://www.jessicabrody.com/2020/11/how-to-write-your-novel-using-the-save-the-cat-beat-sheet/](https://www.jessicabrody.com/2020/11/how-to-write-your-novel-using-the-save-the-cat-beat-sheet/)  
21. Narrative Design | Get Creative Today with Unity, 访问时间为 十一月 25, 2025， [https://getcreativetoday.com/GCT-GDConcepts/p03-playerEngagement/narrative-design/](https://getcreativetoday.com/GCT-GDConcepts/p03-playerEngagement/narrative-design/)  
22. The Secret to Creating Immersive Murder Mysteries \- Save the Cat\!, 访问时间为 十一月 25, 2025， [https://savethecat.com/success-stories/even-immersive-mysteries-need-a-beat-sheet](https://savethecat.com/success-stories/even-immersive-mysteries-need-a-beat-sheet)  
23. The core task of the first three chapters of a web novel | by Mespery | Medium, 访问时间为 十一月 25, 2025， [https://medium.com/@mespery/the-core-task-of-the-first-three-chapters-of-a-web-novel-28d8357b6adb](https://medium.com/@mespery/the-core-task-of-the-first-three-chapters-of-a-web-novel-28d8357b6adb)  
24. Writing Post-Apocalyptic Novels? Learn Basics of Post-Apocalyptic Fiction \- The Urban Writers, 访问时间为 十一月 25, 2025， [https://theurbanwriters.com/blogs/publishing/writing-post-apocalyptic-novels](https://theurbanwriters.com/blogs/publishing/writing-post-apocalyptic-novels)  
25. The Ultimate Guide to Writing a Post-Apocalyptic Novel \- Raindrops Insider, 访问时间为 十一月 25, 2025， [https://raindrops-insider.beehiiv.com/p/the-ultimate-guide-to-writing-a-post-apocalyptic-novel](https://raindrops-insider.beehiiv.com/p/the-ultimate-guide-to-writing-a-post-apocalyptic-novel)  
26. Context engineering in agents \- Docs by LangChain, 访问时间为 十一月 25, 2025， [https://docs.langchain.com/oss/python/langchain/context-engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)  
27. Dynamic Context Injection with Retrieval Augmented Generation \- Newline.co, 访问时间为 十一月 25, 2025， [https://www.newline.co/@zaoyang/dynamic-context-injection-with-retrieval-augmented-generation--68b80921](https://www.newline.co/@zaoyang/dynamic-context-injection-with-retrieval-augmented-generation--68b80921)  
28. Hierarchies & Graph Databases \- by Jim McHugh \- Medium, 访问时间为 十一月 25, 2025， [https://medium.com/@jim.mchugh/hierarchies-graph-databases-e2d7d6c8dd83](https://medium.com/@jim.mchugh/hierarchies-graph-databases-e2d7d6c8dd83)  
29. RulesEngine | A Json based Rules Engine with extensive Dynamic expression support, 访问时间为 十一月 25, 2025， [https://microsoft.github.io/RulesEngine/](https://microsoft.github.io/RulesEngine/)  
30. How I Built a Dynamic Rules Engine Without Writing a Single If-Else: My Discovery of, 访问时间为 十一月 25, 2025， [https://javascript.plainenglish.io/how-i-built-a-dynamic-rules-engine-without-writing-a-single-if-else-my-discovery-of-426055901a86](https://javascript.plainenglish.io/how-i-built-a-dynamic-rules-engine-without-writing-a-single-if-else-my-discovery-of-426055901a86)  
31. Why JSON-Serializable Rules Changed Everything: From Code Chaos to Configuration Clarity \- DEV Community, 访问时间为 十一月 25, 2025， [https://dev.to/crafts69guy/why-json-serializable-rules-changed-everything-from-code-chaos-to-configuration-clarity-2c9](https://dev.to/crafts69guy/why-json-serializable-rules-changed-everything-from-code-chaos-to-configuration-clarity-2c9)  
32. Data, Schema, Ontology and Logic Integration | OUP Journals & Magazine | IEEE Xplore, 访问时间为 十一月 25, 2025， [https://ieeexplore.ieee.org/document/8131754/](https://ieeexplore.ieee.org/document/8131754/)  
33. Storytelling 101: The Dan Harmon Story Circle | Boords, 访问时间为 十一月 25, 2025， [https://boords.com/blog/storytelling-101-the-dan-harmon-story-circle](https://boords.com/blog/storytelling-101-the-dan-harmon-story-circle)  
34. Relevant Search Leveraging Knowledge Graphs with Neo4j, 访问时间为 十一月 25, 2025， [https://neo4j.com/blog/knowledge-graph/relevant-search-knowledge-graphs-neo4j/](https://neo4j.com/blog/knowledge-graph/relevant-search-knowledge-graphs-neo4j/)  
35. Narrative Graph Models \- maetl, 访问时间为 十一月 25, 2025， [https://maetl.net/notes/storyboard/narrative-graph-models](https://maetl.net/notes/storyboard/narrative-graph-models)  
36. Best practices for prompt engineering with the OpenAI API, 访问时间为 十一月 25, 2025， [https://help.openai.com/en/articles/6654000-best-practices-for-prompt-engineering-with-the-openai-api](https://help.openai.com/en/articles/6654000-best-practices-for-prompt-engineering-with-the-openai-api)  
37. Prompt and settings for Story generation using LLMs : r/LocalLLaMA \- Reddit, 访问时间为 十一月 25, 2025， [https://www.reddit.com/r/LocalLLaMA/comments/1fbggqv/prompt\_and\_settings\_for\_story\_generation\_using/](https://www.reddit.com/r/LocalLLaMA/comments/1fbggqv/prompt_and_settings_for_story_generation_using/)