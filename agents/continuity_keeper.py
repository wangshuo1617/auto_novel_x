import json

from utils.llm_client import gemini_client, load_prompt_config

class ContinuityKeeper:
    def __init__(self, db_state: dict, chapter_outline: str, generated_text: str):
        self.db_state = db_state
        self.chapter_outline = chapter_outline
        self.generated_text = generated_text
        self.system_prompt = load_prompt_config("continuity_keeper_prompt", "system")
        chapter_outline_text = (
            self.chapter_outline
            if isinstance(self.chapter_outline, str)
            else json.dumps(self.chapter_outline, ensure_ascii=False, indent=2)
        )
        prepare_data = {
            "db_state": json.dumps(self.db_state, ensure_ascii=False, indent=2),
            "chapter_outline": chapter_outline_text,
            "generated_text": self.generated_text
        }
        self.user_prompt = load_prompt_config("continuity_keeper_prompt", "user", **prepare_data)
        self.schema = load_prompt_config("continuity_keeper_prompt", "json_schema")
        
    def run(self) -> dict:
        response = gemini_client(self.system_prompt, self.user_prompt, self.schema)
        return response