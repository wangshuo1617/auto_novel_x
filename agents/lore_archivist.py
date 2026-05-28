import json

from utils.llm_client import gemini_client, load_prompt_config


class LoreArchivist:
    """
    LoreArchivist（设定史官/档案管理员）
    读取润色后的最新章节正文，抽取摘要/伏笔/新增设定等信息，便于入库检索与后续连贯性维护。
    """

    def __init__(
        self,
        chapter_num: int,
        chapter_title: str,
        final_chapter_text: str,
        previous_story_summary: str = "",
        recent_story_summaries: str = "",
        active_threads_summary: str = "",
        volume_num: int | None = None,
        volume_plan: dict | None = None,
        chapter_outline: dict | None = None,
    ):
        self.chapter_num = chapter_num
        self.chapter_title = chapter_title
        self.final_chapter_text = final_chapter_text
        self.previous_story_summary = previous_story_summary
        self.recent_story_summaries = recent_story_summaries
        self.active_threads_summary = active_threads_summary
        self.volume_num = volume_num
        self.volume_plan = volume_plan or {}
        self.chapter_outline = chapter_outline or {}

        self.system_prompt = load_prompt_config("lore_archivist_prompt", "system")
        prepare_data = {
            "chapter_num": self.chapter_num,
            "chapter_title": self.chapter_title,
            "final_chapter_text": self.final_chapter_text,
            "previous_story_summary": self.previous_story_summary,
            "recent_story_summaries": self.recent_story_summaries,
            "active_threads_summary": self.active_threads_summary,
            "volume_num": self.volume_num or "",
            "volume_plan": json.dumps(self.volume_plan, ensure_ascii=False, indent=2),
            "chapter_outline": json.dumps(self.chapter_outline, ensure_ascii=False, indent=2),
        }
        self.user_prompt = load_prompt_config("lore_archivist_prompt", "user", **prepare_data)
        self.schema = load_prompt_config("lore_archivist_prompt", "json_schema")

    def run(self) -> dict:
        response = gemini_client(self.system_prompt, self.user_prompt, self.schema)
        return response
