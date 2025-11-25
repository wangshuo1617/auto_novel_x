"""
TrendScout (趋势侦察兵) - 市场情报与题材自动化模块

职责：
- 每日爬取起点/番茄排行榜
- 分析热门题材与标签
- 生成趋势分析报告
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import time
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import os
from utils.llm_client import gemini_pro_client, gemini_flash_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QidianScraper:
    """起点中文网爬虫"""
    
    def __init__(self, headless: bool = True):
        """
        初始化爬虫
        
        Args:
            headless: 是否使用无头模式
        """
        self.options = Options()
        if headless:
            self.options.add_argument('--headless')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-blink-features=AutomationControlled')
        self.options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        self.driver = None
        
    def __enter__(self):
        """上下文管理器入口"""
        try:
            self.driver = webdriver.Chrome(options=self.options)
            return self
        except Exception as e:
            logger.error(f"Chrome驱动初始化失败: {e}")
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        if self.driver:
            self.driver.quit()
    
    def _get_tags_from_detail_page(self, book_url: str) -> List[str]:
        """
        从小说详情页获取标签
        
        Args:
            book_url: 小说详情页URL
            
        Returns:
            标签列表
        """
        tags = []
        try:
            # 访问详情页
            self.driver.get(book_url)
            time.sleep(1)  # 等待页面加载
            
            # 解析页面
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # 根据图片描述，标签在 <p class="all-label"> 中的 <a> 标签
            # 尝试多种可能的选择器
            label_elem = soup.select_one('p.all-label, .all-label, .intro-honor-label .all-label')
            
            if label_elem:
                # 提取所有 <a> 标签，href 包含 /all/tag/ 或 /tag/
                tag_links = label_elem.select('a[href*="/all/tag"], a[href*="/tag"]')
                for tag_link in tag_links:
                    tag_text = tag_link.text.strip()
                    if tag_text:
                        tags.append(tag_text)
            
            # 如果没找到，尝试其他可能的选择器
            if not tags:
                # 尝试查找包含标签的链接（href包含tag）
                tag_links = soup.select('a[href*="/all/tag"], a[href*="/tag"]')
                for tag_link in tag_links:
                    tag_text = tag_link.text.strip()
                    # 过滤掉明显不是标签的文本（如"小说"、"更多"等）
                    if tag_text and len(tag_text) <= 10 and tag_text not in ['小说', '更多', '查看']:
                        tags.append(tag_text)
            
            # 去重
            tags = list(dict.fromkeys(tags))
            
        except Exception as e:
            logger.warning(f"从详情页 {book_url} 获取标签失败: {e}")
        
        return tags
    
    def scrape_rankings(self, rank_type: str = "monthly", max_books: int = 50) -> List[Dict]:
        """
        爬取排行榜数据
        
        Args:
            rank_type: 排行榜类型 ("monthly"月票榜, "recommend"推荐榜, "new"新书榜)
            max_books: 最大爬取数量
            
        Returns:
            书籍信息列表
        """
        books = []
        try:
            # 构建URL
            url_map = {
                "monthly": "https://www.qidian.com/rank/yuepiao/",
                "recommend": "https://www.qidian.com/rank/recom/",
                "new": "https://www.qidian.com/rank/signnewbook/",
            }
            url = url_map.get(rank_type, url_map["monthly"])
            
            logger.info(f"开始爬取起点{rank_type}榜: {url}")
            self.driver.get(url)
            
            # 等待页面加载
            time.sleep(3)
            
            # 等待内容加载
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "book-img-text"))
                )
            except Exception as e:
                logger.warning(f"等待页面元素超时: {e}")
            
            # 解析页面
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            book_list = soup.select('.book-img-text li')
            
            logger.info(f"找到 {len(book_list)} 本书籍")
            
            for idx, book in enumerate(book_list[:max_books]):
                try:
                    # 提取书名
                    title_elem = book.select_one('h2 a, .book-mid-info h2 a')
                    title = title_elem.text.strip() if title_elem else "未知"
                    
                    # 提取链接
                    link = title_elem.get('href', '') if title_elem else ''
                    if link and not link.startswith('http'):
                        link = f"https:{link}" if link.startswith('//') else f"https://www.qidian.com{link}"
                    
                    # 提取作者
                    author_elem = book.select_one('.author a, .book-mid-info .author a')
                    author = author_elem.text.strip() if author_elem else "未知"
                    
                    # 提取简介
                    intro_elem = book.select_one('.intro, .book-mid-info .intro')
                    intro = intro_elem.text.strip() if intro_elem else ""
                    
                    # 提取标签
                    tags = []
                    # 如果排行榜页面没有标签，且需要从详情页获取
                    if link:
                        tags = self._get_tags_from_detail_page(link)
                        # 添加小延迟，避免请求过快
                        time.sleep(0.5)
                    
                    # 去重
                    tags = list(dict.fromkeys(tags))
                    
                    # 提取更新信息
                    update_elem = book.select_one('.update, .book-mid-info .update')
                    update_info = update_elem.text.strip() if update_elem else ""
                    
                    # 提取推荐票/月票数（如果可见）
                    vote_elem = book.select_one('.total, .book-mid-info .total')
                    votes = vote_elem.text.strip() if vote_elem else ""
                    
                    book_data = {
                        "title": title,
                        "author": author,
                        "intro": intro,
                        "tags": tags,
                        "link": link,
                        "update_info": update_info,
                        "votes": votes,
                        "rank": idx + 1,
                        "timestamp": datetime.now().isoformat(),
                        "platform": "qidian"
                    }
                    books.append(book_data)
                    
                except Exception as e:
                    logger.warning(f"解析第{idx+1}本书时出错: {e}")
                    continue
            
            logger.info(f"成功爬取 {len(books)} 本书籍")
            return books
            
        except Exception as e:
            logger.error(f"爬取过程中出错: {e}")
            return books


class TrendAnalyzer:
    """趋势分析器 - 使用LLM进行语义聚类分析"""
    
    def __init__(self, llm_client=None):
        """
        初始化分析器
        
        Args:
            llm_client: LLM客户端（如OpenAI、DeepSeek等），如果为None则使用本地分析
        """
        self.llm_client = llm_client
    
    def analyze_trends(self, books_data: List[Dict], analysis_type: str = "llm") -> Dict:
        """
        分析趋势
        
        Args:
            books_data: 书籍数据列表
            analysis_type: 分析类型 ("llm"使用LLM, "local"本地统计)
            
        Returns:
            趋势分析报告
        """
        if analysis_type == "llm" and self.llm_client:
            return self._llm_analyze(books_data)
        else:
            return self._local_analyze(books_data)
    
    def _local_analyze(self, books_data: List[Dict]) -> Dict:
        """
        本地统计分析（不使用LLM）
        
        Args:
            books_data: 书籍数据列表
            
        Returns:
            趋势分析报告
        """
        # 统计标签频率
        tag_counter = {}
        platform_counter = {}
        
        for book in books_data:
            platform = book.get("platform", "unknown")
            platform_counter[platform] = platform_counter.get(platform, 0) + 1
            
            tags = book.get("tags", [])
            for tag in tags:
                tag_counter[tag] = tag_counter.get(tag, 0) + 1
        
        # 找出热门标签
        top_tags = sorted(tag_counter.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # 分析题材组合（简单的共现分析）
        tag_combinations = {}
        for book in books_data:
            tags = book.get("tags", [])
            if len(tags) >= 2:
                # 生成标签对
                for i in range(len(tags)):
                    for j in range(i+1, len(tags)):
                        combo = tuple(sorted([tags[i], tags[j]]))
                        tag_combinations[combo] = tag_combinations.get(combo, 0) + 1
        
        top_combinations = sorted(tag_combinations.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "analysis_time": datetime.now().isoformat(),
            "total_books": len(books_data),
            "platform_distribution": platform_counter,
            "top_tags": [{"tag": tag, "count": count} for tag, count in top_tags],
            "top_combinations": [{"tags": list(combo), "count": count} for combo, count in top_combinations],
            "recommendations": self._generate_recommendations(top_tags, top_combinations)
        }
    
    def _llm_analyze(self, books_data: List[Dict]) -> Dict:
        """
        使用LLM进行深度分析
        
        Args:
            books_data: 书籍数据列表
            
        Returns:
            LLM生成的分析报告
        """
        # 构建提示词
        prompt = self._build_analysis_prompt(books_data)
        
        try:
            # 调用LLM（这里需要根据实际的LLM客户端调整）
            if hasattr(self.llm_client, 'invoke'):
                response = self.llm_client.invoke(prompt)
                print(response)
                result = response.content if hasattr(response, 'content') else str(response)
            else:
                # 降级到本地分析
                logger.warning("LLM客户端不可用，降级到本地分析")
                return self._local_analyze(books_data)
            
            # 尝试解析JSON
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                # 如果不是JSON，包装结果
                return {
                    "analysis_time": datetime.now().isoformat(),
                    "llm_analysis": result,
                    "raw_data": books_data[:10]  # 只保留前10条原始数据
                }
        except Exception as e:
            logger.error(f"LLM分析失败: {e}，降级到本地分析")
            return self._local_analyze(books_data)
    
    def _build_analysis_prompt(self, books_data: List[Dict]) -> str:
        """
        构建分析提示词
        
        Args:
            books_data: 书籍数据列表
            
        Returns:
            提示词字符串
        """
        # 准备数据摘要
        books_summary = []
        for book in books_data[:50]:  # 限制前50本
            books_summary.append({
                "title": book.get("title", ""),
                "tags": book.get("tags", []),
                "intro": book.get("intro", "")[:200]  # 限制简介长度
            })
        
        prompt = f"""Role: 网文大数据分析师

Input: 最近24小时起点排行榜Top 50书籍简介及标签列表（JSON格式）。

数据：
{json.dumps(books_summary, ensure_ascii=False, indent=2)}

Task:
1. 识别当前最热门的3个"题材组合"（如：重生+神豪+直播）。
2. 分析"蓝海"题材：即需求量大（搜索多）但供给少（上榜书少）的领域。
3. 为每个热门题材组合推荐主角人设原型。

Output: 生成一份JSON报告，包含以下字段：
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

请严格按照JSON格式输出，不要包含其他文字。不要包括前后的json标识符。"""
        
        return prompt
    
    def _generate_recommendations(self, top_tags: List, top_combinations: List) -> List[Dict]:
        """
        生成推荐建议
        
        Args:
            top_tags: 热门标签列表
            top_combinations: 热门组合列表
            
        Returns:
            推荐列表
        """
        recommendations = []
        
        # 基于热门标签生成推荐
        if top_tags:
            top_tag = top_tags[0][0]
            recommendations.append({
                "type": "热门标签",
                "suggestion": f"当前最热门标签是'{top_tag}'，建议结合此标签创作",
                "confidence": "高"
            })
        
        # 基于组合生成推荐
        if top_combinations:
            combo = top_combinations[0]
            recommendations.append({
                "type": "题材组合",
                "suggestion": f"热门组合：{' + '.join(combo[0])}，可考虑采用此组合",
                "confidence": "中"
            })
        
        return recommendations


class TrendScout:
    """趋势侦察兵主类 - 整合爬虫和分析器"""
    
    def __init__(self, llm_client=None, headless: bool = True):
        """
        初始化TrendScout
        
        Args:
            llm_client: LLM客户端（可选）
            headless: 是否使用无头浏览器
        """
        self.llm_client = llm_client
        self.headless = headless
        self.analyzer = TrendAnalyzer(llm_client)
    
    def scout(self, platforms: List[str] = ["qidian"], rank_types: List[str] = None, 
              max_books: int = 50, use_llm: bool = False) -> Dict:
        """
        执行侦察任务
        
        Args:
            platforms: 平台列表 ["qidian"]
            rank_types: 排行榜类型列表，如果为None则使用默认值
            max_books: 每个平台最大爬取数量
            use_llm: 是否使用LLM进行深度分析
            
        Returns:
            完整的侦察报告
        """
        all_books = []
        
        # 默认排行榜类型
        if rank_types is None:
            rank_types = ["monthly"] if "qidian" in platforms else ["new"]
        
        # 爬取起点
        if "qidian" in platforms:
            logger.info("开始爬取起点中文网...")
            try:
                with QidianScraper(headless=self.headless) as scraper:
                    for rank_type in rank_types:
                        books = scraper.scrape_rankings(rank_type=rank_type, max_books=max_books)
                        all_books.extend(books)
                        time.sleep(2)  # 避免请求过快
            except Exception as e:
                logger.error(f"爬取起点失败: {e}")
        
        # 分析趋势
        logger.info(f"开始分析 {len(all_books)} 本书籍的趋势...")
        analysis = self.analyzer.analyze_trends(
            all_books, 
            analysis_type="llm" if use_llm and self.llm_client else "local"
        )
        
        # 生成完整报告
        report = {
            "scout_time": datetime.now().isoformat(),
            "platforms": platforms,
            "total_books_scraped": len(all_books),
            "raw_data": all_books,
            "trend_analysis": analysis
        }
        
        return report
    
    def save_report(self, report: Dict, filepath: str = None) -> str:
        """
        保存报告到文件
        
        Args:
            report: 报告字典
            filepath: 文件路径，如果为None则自动生成
            
        Returns:
            保存的文件路径
        """
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"trend_report_{timestamp}.json"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"报告已保存到: {filepath}")
        return filepath


# 使用示例
if __name__ == "__main__":
    # 示例：不使用LLM的本地分析
    scout = TrendScout(llm_client=gemini_flash_client, headless=True)
    report = scout.scout(
        platforms=["qidian"],
        rank_types=["monthly","recommend","new"],
        max_books=20,
        use_llm=True
    )
    
    # 保存报告
    scout.save_report(report)
    
    # 打印摘要
    print("\n=== 趋势分析摘要 ===")
    print(f"爬取书籍总数: {report['total_books_scraped']}")
    if "trend_analysis" in report:
        analysis = report["trend_analysis"]
        print(f"\n热门标签Top 5:")
        for tag_info in analysis.get("top_tags", [])[:5]:
            print(f"  - {tag_info['tag']}: {tag_info['count']}次")
        
        print(f"\n热门组合Top 3:")
        for combo_info in analysis.get("top_combinations", [])[:3]:
            print(f"  - {' + '.join(combo_info['tags'])}: {combo_info['count']}次")

