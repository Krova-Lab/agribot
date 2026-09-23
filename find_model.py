import os
from dotenv import load_dotenv
from config.database import PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env")
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

try:
    from google import genai
    client = genai.Client(api_key=api_key)
    print("--- Searching through google-genai ---")
    for m in client.models.list():
        if "embedContent" in m.supported_actions:
            print("✅ Allowed embedding model:", m.name)
except Exception as e:
    print("google-genai error:", e)

try:
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    print("--- Searching through google.generativeai ---")
    for m in genai.list_models():
        if "embedContent" in m.supported_generation_methods:
            print("✅ Allowed embedding model:", m.name)
except Exception as e:
    print("google.generativeai error:", e)
