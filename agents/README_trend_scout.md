# TrendScout 模块使用说明

## 概述

TrendScout（趋势侦察兵）是AutoNovel-X系统的市场情报模块，负责：
- 爬取起点中文网和番茄小说的排行榜数据
- 分析热门题材与标签
- 生成趋势分析报告

## 快速开始

### 基本使用（不使用LLM）

```python
from agents.trend_scout import TrendScout

# 创建TrendScout实例
scout = TrendScout(headless=True)

# 执行侦察任务
report = scout.scout(
    platforms=["qidian"],      # 平台：qidian（起点）或 fanqie（番茄）
    rank_types=["monthly"],    # 排行榜类型：monthly（月票榜）、recommend（推荐榜）、new（新书榜）
    max_books=50,              # 每个平台最大爬取数量
    use_llm=False              # 是否使用LLM进行深度分析
)

# 保存报告
scout.save_report(report, "trend_report.json")

# 查看分析结果
print(f"爬取书籍总数: {report['total_books_scraped']}")
analysis = report['trend_analysis']
print(f"热门标签: {analysis['top_tags']}")
```

### 使用LLM进行深度分析

```python
from langchain_openai import ChatOpenAI
from agents.trend_scout import TrendScout

# 初始化LLM客户端（需要配置API密钥）
llm_client = ChatOpenAI(
    model="gpt-4o",
    api_key="your-api-key"
)

# 创建TrendScout实例（传入LLM客户端）
scout = TrendScout(llm_client=llm_client, headless=True)

# 执行侦察任务（启用LLM分析）
report = scout.scout(
    platforms=["qidian", "fanqie"],
    max_books=50,
    use_llm=True  # 启用LLM分析
)

# 查看LLM生成的分析报告
print(report['trend_analysis'])
```

## 类说明

### QidianScraper
起点中文网爬虫类

**方法：**
- `scrape_rankings(rank_type="monthly", max_books=50)`: 爬取排行榜数据

**参数：**
- `rank_type`: 排行榜类型
  - `"monthly"`: 月票榜
  - `"recommend"`: 推荐榜
  - `"new"`: 新书榜
- `max_books`: 最大爬取数量

**返回：**
书籍信息列表，每个元素包含：
- `title`: 书名
- `author`: 作者
- `intro`: 简介
- `tags`: 标签列表
- `link`: 书籍链接
- `update_info`: 更新信息
- `votes`: 票数
- `rank`: 排名
- `timestamp`: 时间戳
- `platform`: 平台标识

### FanqieScraper
番茄小说爬虫类（注意：需要根据实际页面结构调整选择器）

**方法：**
- `scrape_rankings(rank_type="new", max_books=50)`: 爬取排行榜数据

### TrendAnalyzer
趋势分析器

**方法：**
- `analyze_trends(books_data, analysis_type="llm")`: 分析趋势
  - `analysis_type="local"`: 本地统计分析（标签频率、组合分析）
  - `analysis_type="llm"`: 使用LLM进行深度语义分析

### TrendScout
主类，整合爬虫和分析器

**方法：**
- `scout(platforms, rank_types, max_books, use_llm)`: 执行完整的侦察任务
- `save_report(report, filepath)`: 保存报告到JSON文件

## 报告结构

```json
{
  "scout_time": "2025-11-25T12:00:00",
  "platforms": ["qidian"],
  "total_books_scraped": 50,
  "raw_data": [...],
  "trend_analysis": {
    "analysis_time": "2025-11-25T12:00:00",
    "total_books": 50,
    "platform_distribution": {"qidian": 50},
    "top_tags": [
      {"tag": "系统流", "count": 15},
      ...
    ],
    "top_combinations": [
      {"tags": ["系统流", "签到"], "count": 8},
      ...
    ],
    "recommendations": [...]
  }
}
```

## 注意事项

1. **Chrome驱动**: 需要安装Chrome浏览器和ChromeDriver，或使用selenium-manager自动管理
2. **反爬虫**: 起点和番茄都有反爬机制，建议：
   - 设置合理的请求间隔
   - 使用代理（如需要）
   - 遵守robots.txt
3. **页面结构变化**: 如果网站改版，需要更新CSS选择器
4. **LLM分析**: 使用LLM分析需要配置API密钥，会产生费用

## 环境要求

- Python 3.12+
- Chrome浏览器
- ChromeDriver（或使用selenium-manager）
- 相关依赖包（见requirements.txt）

## 示例输出

```
=== 趋势分析摘要 ===
爬取书籍总数: 50

热门标签Top 5:
  - 系统流: 15次
  - 签到: 12次
  - 重生: 10次
  - 神豪: 8次
  - 直播: 6次

热门组合Top 3:
  - 系统流 + 签到: 8次
  - 重生 + 神豪: 5次
  - 系统流 + 直播: 4次
```

