import os
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
response = requests.get(url, timeout=30)

if response.status_code == 200:
    data = response.json()
    print("Available models for the configured API key:")
    for model in data.get('models', []):
        name = model.get('name')
        methods = model.get('supportedGenerationMethods', [])
        if 'embedContent' in methods:
            print(f" - [EMBEDDING] {name} (methods: {methods})")
        else:
            print(f" - {name} (methods: {methods})")
else:
    print(f"Error while querying Google models: HTTP {response.status_code}")
