from utils.llm_client import gemini_client,load_prompt_config

class WorldArchitect:
    def __init__(self, trend_analysis: dict, human_idea: str, review_feedback: str = ""):
        self.trend_analysis = trend_analysis
        self.human_idea = human_idea
        self.review_feedback = review_feedback
        
    def run(self) -> dict:
        system_prompt = load_prompt_config("world_architect_prompt", "system")
        world_json = {
            "trend_analysis": self.trend_analysis,
            "human_idea": self.human_idea,
            "review_feedback": self.review_feedback,
        }
        user_prompt = load_prompt_config("world_architect_prompt", "user", **world_json)
        schema = load_prompt_config("world_architect_prompt", "json_schema")
        response = gemini_client(system_prompt, user_prompt, schema)
        return response