import os
from dotenv import load_dotenv
from google import genai

load_dotenv(os.path.expanduser("~/agribot/.env"))
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

print("--- Allowed text models ---")
for m in client.models.list():
    if "generateContent" in m.supported_actions:
        print("✅", m.name)
