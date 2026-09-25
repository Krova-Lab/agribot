import os
import requests
from google import genai
from google.genai import types
from dotenv import load_dotenv
from config.prompt_loader import load_prompts, render_prompt
from rag_search import retrieve_rag

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
plantnet_key = os.getenv("PLANTNET_API_KEY")

client = genai.Client(api_key=api_key) if api_key else None

PROMPTS = load_prompts()

def get_weather_history(lat, lon):
    """Fetch the previous seven days of weather from Open-Meteo (no API key)."""
    from datetime import date, timedelta
    end_d = date.today() - timedelta(days=1)
    start_d = end_d - timedelta(days=7)
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={start_d}&end_date={end_d}&daily=precipitation_sum"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return res.json().get("daily", {})
    except Exception as e:
        print(f"Open-Meteo error: {type(e).__name__}")
    return {}

def query_rag_knowledge(query_text, limit=2):
    """Use the canonical provenance-aware retrieval implementation."""
    result = retrieve_rag(query_text, limit=limit)
    return [
        {"source": source.title, "content": source.content, "source_url": source.url}
        for source in result.sources
    ]

def analyze_crop_issue(image_path, lat, lon, user_text):
    """Orchestrate the complete diagnosis workflow (APIs + RAG + Gemini)."""
    if client is None:
        raise RuntimeError("Gemini credentials are not configured")
    print("1. Retrieving contextual data (weather and soil)...")
    weather = get_weather_history(lat, lon)
    from api_clients import get_soil_data_with_fallback
    soil = get_soil_data_with_fallback(lat, lon)
    
    print("2. Querying the local knowledge base (RAG)...")
    rag_docs = query_rag_knowledge(user_text)
    
    context_str = "\n".join([f"[{d['source']}] {d['content']}" for d in rag_docs])
    
    print("3. Generating the Gemini synthesis...")
    prompt = render_prompt(
        PROMPTS["workflow_prompt"],
        lat=lat,
        lon=lon,
        soil=soil,
        weather=weather,
        context_str=context_str,
        user_text=user_text,
    )
    
    # Use gemini-3.6-flash as the inference model
    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=[prompt],
        config=types.GenerateContentConfig(tools=[])
    )
    
    return response.text

if __name__ == "__main__":
    sample_lat = 11.5564
    sample_lon = 104.9282
    sample_query = "Feuilles jaunissantes sur mon riz en zone pluviale"
    
    print(f"Starting analysis test for: '{sample_query}'...\n")
    result = analyze_crop_issue(None, sample_lat, sample_lon, sample_query)
    print("Analysis result:\n")
    print(result)
