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
from typing import List, Dict, Optional
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from utils.llm_client import gemini_client,load_prompt_config

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
            print(f"Chrome驱动初始化失败: {e}")
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
            print(f"从详情页 {book_url} 获取标签失败: {e}")
        
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
            
            print(f"开始爬取起点{rank_type}榜: {url}")
            self.driver.get(url)
            
            # 等待页面加载
            time.sleep(3)
            
            # 等待内容加载
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "book-img-text"))
                )
            except Exception as e:
                print(f"等待页面元素超时: {e}")
            
            # 解析页面
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            book_list = soup.select('.book-img-text li')
            
            print(f"找到 {len(book_list)} 本书籍")
            
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
                    print(f"解析第{idx+1}本书时出错: {e}")
                    continue
            
            print(f"成功爬取 {len(books)} 本书籍")
            return books
            
        except Exception as e:
            print(f"爬取过程中出错: {e}")
            return books


class TrendAnalyzer:
    """趋势分析器 - 使用LLM进行语义聚类分析"""

    def analyze_trends(self, books_data: List[Dict]) -> Dict:
        books_summary = []
        for book in books_data[:50]:  # 限制前50本
            books_summary.append({
                "title": book.get("title", ""),
                "tags": book.get("tags", []),
                "intro": book.get("intro", "")[:200]  # 限制简介长度
            })
        
        system_prompt = load_prompt_config("trend_scout_prompt", "system")
        user_prompt = load_prompt_config("trend_scout_prompt", "user", book_data=json.dumps(books_summary, ensure_ascii=False, indent=2))
        schema = load_prompt_config("trend_scout_prompt", "json_schema")
        response = gemini_client(system_prompt, user_prompt, schema)
        return response       
        
class TrendScout:
    """趋势侦察兵主类 - 整合爬虫和分析器"""
    
    def __init__(self, headless: bool = True):
        """
        初始化TrendScout
        
        Args:
            llm_client: LLM客户端（可选）
            headless: 是否使用无头浏览器
        """
        self.headless = headless
        self.analyzer = TrendAnalyzer()
    
    def scout(self, platforms: List[str] = ["qidian"], rank_types: List[str] = None, 
              max_books: int = 50,analysis_only: bool = False) -> Dict:
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
            print("开始爬取起点中文网...")
            try:
                with QidianScraper(headless=self.headless) as scraper:
                    for rank_type in rank_types:
                        books = scraper.scrape_rankings(rank_type=rank_type, max_books=max_books)
                        all_books.extend(books)
                        time.sleep(2)  # 避免请求过快
            except Exception as e:
                print(f"爬取起点失败: {e}")
        
        # 分析趋势
        print(f"开始分析 {len(all_books)} 本书籍的趋势...")
        analysis = self.analyzer.analyze_trends(
            all_books)
        
        # 生成完整报告
        report = {
            "scout_time": datetime.now().isoformat(),
            "platforms": platforms,
            "total_books_scraped": len(all_books),
            "raw_data": all_books,
            "trend_analysis": analysis
        }
        if analysis_only:
            return analysis
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
        
        print(f"报告已保存到: {filepath}")
        return filepath


# 使用示例
if __name__ == "__main__":
    # 示例：不使用LLM的本地分析
    scout = TrendScout()
    report = scout.scout(
        platforms=["qidian"],
        rank_types=["monthly","recommend","new"],
        max_books=20,
        analysis_only=True
    )
    print(report)
    # 保存报告
    scout.save_report(report)
    
