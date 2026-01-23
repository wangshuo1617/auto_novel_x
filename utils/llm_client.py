from google import genai
from google.genai import types
import json,os,sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
from config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)

def gemini_client(system_prompt: str, user_prompt: str, response_schema: dict,temperature: float = 0.7) -> str:
  config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_schema=response_schema,
        temperature=temperature,
    )
  response = client.models.generate_content(
    model="gemini-3-pro-preview",
    contents=user_prompt,
    config=config
  )
  result = json.loads(response.text)
  return result

def load_prompt_config(template_name: str,type: str, **kwargs) -> str:
  import importlib
  module = importlib.import_module(f"agents.prompt.{template_name}")
  if "schema" not in type:
    type = f"{type}_prompt"
    return getattr(module, type).format(**kwargs)
  else:
    type = "json_schema"
    return getattr(module, type)
    
if __name__ == "__main__":
  system_prompt = load_prompt_config("world_architect_prompt", "system")
  user_prompt = load_prompt_config("world_architect_prompt", "user", trend_analysis="aaaaaaaaaa")
  schema = load_prompt_config("world_architect_prompt", "json_schema")
  result = gemini_client(system_prompt, user_prompt,schema)
  print(result)