from utils.llm_client import gemini_client,load_prompt_config
import json

class ElementDesigner:
    def __init__(self, world_setting: dict):
        self.world_setting = world_setting

    def run(self, mode: str = "initial", request_payload: dict = None, review_feedback: str = "") -> dict:
        system_prompt = load_prompt_config("element_designer_prompt", "system")
        schema = load_prompt_config("element_designer_prompt", "json_schema")

        if mode == "initial":
            user_prompt = load_prompt_config(
                "element_designer_prompt",
                "initial",
                world_setting=json.dumps(self.world_setting, ensure_ascii=False, indent=2),
                review_feedback=review_feedback,
            )
        elif mode == "addon":
            payload = {"review_feedback": review_feedback}
            for key, value in (request_payload or {}).items():
                if isinstance(value, (dict, list)):
                    payload[key] = json.dumps(value, ensure_ascii=False, indent=2)
                else:
                    payload[key] = value
            user_prompt = load_prompt_config("element_designer_prompt", "addon", **payload)
        else:
            raise ValueError(f"Unknown mode: {mode}")

        response = gemini_client(system_prompt, user_prompt, schema)
        return response