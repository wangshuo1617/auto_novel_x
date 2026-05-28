from utils.llm_client import gemini_client,load_prompt_config

class StylePolisher:
    def __init__(self, draft_data: dict):
        self.draft_data = draft_data
        self.system_prompt = load_prompt_config("style_polish_prompt", "system")
        self.user_prompt = load_prompt_config("style_polish_prompt", "user", raw_draft = self.draft_data)
        self.schema = load_prompt_config("style_polish_prompt", "json_schema")
        
    def run(self) -> dict:
        response = gemini_client(self.system_prompt, self.user_prompt, self.schema)
        return response