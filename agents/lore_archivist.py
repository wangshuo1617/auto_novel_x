import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import json
from datetime import datetime
from utils.llm_client import gemini_client, load_prompt_config


class LoreArchivist:
    """
    LoreArchivist（设定史官/档案管理员）
    读取润色后的最新章节正文，抽取摘要/伏笔/新增设定等信息，便于入库检索与后续连贯性维护。
    """

    def __init__(self, chapter_num: int, chapter_title: str, final_chapter_text: str):
        self.chapter_num = chapter_num
        self.chapter_title = chapter_title
        self.final_chapter_text = final_chapter_text

        self.system_prompt = load_prompt_config("lore_archivist_prompt", "system")
        prepare_data = {
            "chapter_num": self.chapter_num,
            "chapter_title": self.chapter_title,
            "final_chapter_text": self.final_chapter_text,
        }
        self.user_prompt = load_prompt_config("lore_archivist_prompt", "user", **prepare_data)
        self.schema = load_prompt_config("lore_archivist_prompt", "json_schema")

    def run(self) -> dict:
        response = gemini_client(self.system_prompt, self.user_prompt, self.schema)
        return response

    # 兼容旧调用：不再直接运行 gemini_client
    def engineer(self) -> dict:
        return self.run()

    def save_lore_record(self, output_data: dict, filepath: str = None) -> str:
        if filepath is None:
            filepath = f"lore_record_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(output_data["output_data"])
        return filepath


if __name__ == "__main__":
    # 简单示例（请根据你的真实数据替换）
    chapter_num = 1
    chapter_title = "开局一座破庙"
    final_chapter_text = "主角在破庙中苏醒，发现香火可以转化为力量……"

    archivist = LoreArchivist(chapter_num, chapter_title, final_chapter_text)
    record = archivist.run()
    print(record)
    archivist.save_lore_record(record)

