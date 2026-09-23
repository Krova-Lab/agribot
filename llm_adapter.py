import os
import logging
from google import genai
from google.genai import types
from config.prompt_loader import load_prompts
from config.database import PROJECT_ROOT

# Suppress the informational AFC warning emitted by the google-genai SDK
logging.getLogger("google_genai.models").setLevel(logging.ERROR)

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key)

DEFAULT_MODEL = "gemini-3.6-flash"
PROMPTS = load_prompts()

def ask_llm(prompt: str, image_bytes: bytes = None, media_bytes: bytes = None, mime_type: str = "image/jpeg", model_name: str = DEFAULT_MODEL, temperature: float = 0.2):
    try:
        contents = []
        payload = media_bytes if media_bytes is not None else image_bytes
        if payload:
            contents.append(types.Part.from_bytes(data=payload, mime_type=mime_type))
        contents.append(prompt)

        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=temperature,
                tool_config={"function_calling_config": {"mode": "NONE"}}
            )
        )
        return response.text, model_name
    except Exception as e:
        print(f"[LLM ERROR] Model {model_name}: {e}")
        return None, model_name

if __name__ == "__main__":
    res, mod = ask_llm("Dis bonjour en une ligne.")
    print(f"Model: {mod}\nResponse: {res}")
