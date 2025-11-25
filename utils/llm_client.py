from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
load_dotenv()

gemini_flash_client = ChatOpenAI(
  api_key=os.getenv("OPENROUTER_API_KEY"),
  base_url="https://openrouter.ai/api/v1",
  model="google/gemini-2.5-flash"
)

gemini_pro_client = ChatOpenAI(
  api_key=os.getenv("OPENROUTER_API_KEY"),
  base_url="https://openrouter.ai/api/v1",
  model="google/gemini-3-pro-preview"
)

if __name__ == "__main__":
    print(gemini_pro_client.invoke("Hello, how are you?").content)