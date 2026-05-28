import json
from utils.llm_client import gemini_client, load_prompt_config


class SimulatedReader:
    """
    SimulatedReader（模拟读者/试毒员）
    对大纲或正文做读者视角的“毒点扫描 + 爽感评估”，输出可执行的整改意见。
    """

    def __init__(
        self,
        genre: str,
        content_to_review: str,
        review_stage: str = "chapter_draft",
        context_payload: dict | None = None,
        evaluation_focus: str = "",
    ):
        self.genre = genre
        self.content_to_review = content_to_review
        self.review_stage = review_stage
        self.context_payload = context_payload or {}
        self.evaluation_focus = evaluation_focus

        self.system_prompt = load_prompt_config("simulated_reader_prompt", "system")
        self.user_prompt = load_prompt_config(
            "simulated_reader_prompt",
            "user",
            genre=self.genre,
            review_stage=self.review_stage,
            evaluation_focus=self.evaluation_focus,
            context_payload=json.dumps(self.context_payload, ensure_ascii=False, indent=2),
            content_to_review=self.content_to_review,
        )
        self.schema = load_prompt_config("simulated_reader_prompt", "json_schema")

    def run(self) -> dict:
        response = gemini_client(self.system_prompt, self.user_prompt, self.schema)
        return response
