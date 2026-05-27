from google import genai
from google.genai import types
import json,os,sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
from config import GEMINI_API_KEY
from utils.prompt_presets import load_prompt_template

_client = None


def _get_client():
  global _client
  if _client is not None:
    return _client
  if not GEMINI_API_KEY:
    raise ValueError("Missing GEMINI_API_KEY in environment.")
  _client = genai.Client(api_key=GEMINI_API_KEY)
  return _client

def gemini_client(system_prompt: str, user_prompt: str, response_schema: dict,temperature: float = 0.7) -> str:
  config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_schema=response_schema,
        temperature=temperature,
    )
  response = _get_client().models.generate_content(
    model="gemini-3-pro-preview",
    contents=user_prompt,
    config=config
  )
  result = json.loads(response.text)
  return result

def load_prompt_config(template_name: str,type: str, **kwargs) -> str:
  template_config = load_prompt_template(template_name)
  if "schema" not in type:
    key = f"{type}_prompt"
    if key not in template_config:
      raise ValueError(f"{template_name} 缺少 prompt 字段: {key}")
    return template_config[key].format(**kwargs)
  key = "json_schema"
  if key not in template_config:
    raise ValueError(f"{template_name} 缺少 schema 字段: {key}")
  return template_config[key]
    
if __name__ == "__main__":
  system_prompt = load_prompt_config("world_architect_prompt", "system")
  user_prompt = load_prompt_config("world_architect_prompt", "user", trend_analysis="aaaaaaaaaa")
  schema = load_prompt_config("world_architect_prompt", "json_schema")
  result = gemini_client(system_prompt, user_prompt,schema)
  print(result)