import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import datetime
from utils.llm_client import gemini_client, load_prompt_config


class SimulatedReader:
    """
    SimulatedReader（模拟读者/试毒员）
    对大纲或正文做读者视角的“毒点扫描 + 爽感评估”，输出可执行的整改意见。
    """

    def __init__(self, genre: str, content_to_review: str):
        self.genre = genre
        self.content_to_review = content_to_review

        self.system_prompt = load_prompt_config("simulated_reader_prompt", "system")
        self.user_prompt = load_prompt_config(
            "simulated_reader_prompt",
            "user",
            genre=self.genre,
            content_to_review=self.content_to_review,
        )
        self.schema = load_prompt_config("simulated_reader_prompt", "json_schema")

    def run(self) -> dict:
        response = gemini_client(self.system_prompt, self.user_prompt, self.schema)
        return response

    def save_review(self, output_data: dict, filepath: str = None) -> str:
        if filepath is None:
            filepath = f"reader_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(output_data["output_data"])
        return filepath


if __name__ == "__main__":
    # 简单示例（请根据你的真实数据替换）
    genre = "玄幻/系统流"
    content_to_review = "主角被嘲笑后隐忍三章，最后轻轻打了反派一拳……"
    reader = SimulatedReader(genre, content_to_review)
    review = reader.run()
    print(review)
    reader.save_review(review)

