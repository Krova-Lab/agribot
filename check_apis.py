import os
import sys
import requests
import psycopg2
from dotenv import load_dotenv
from google import genai
from config.database import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

print("--- [HEALTHCHECK] Starting Krova Agribot ecosystem checks ---")

# 1. Check PostgreSQL & pgvector (correct system-table extname handling)
try:
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, connect_timeout=3)
    cur = conn.cursor()
    cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
    if cur.fetchone():
        print("[OK] PostgreSQL and pgvector are operational.")
    else:
        print("[WARNING] PostgreSQL is connected but the 'vector' extension is missing.")
    cur.close()
    conn.close()
except Exception as e:
    print(f"[ERROR] PostgreSQL connection failed: {e}")

# 2. Check the Gemini API
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
        print("[ERROR] Gemini API key not found in .env")
else:
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model='gemini-3.6-flash', contents="Test de vie.")
        if response.text:
            print("[OK] API Gemini (GenAI SDK) active et fonctionnelle.")
    except Exception as e:
        print(f"[ERROR] Gemini request failed: {e}")

# 3. Check Open-Meteo (archive)
try:
    res = requests.get("https://archive-api.open-meteo.com/v1/archive?latitude=11.5564&longitude=104.9282&start_date=2026-08-26&end_date=2026-09-02&daily=precipitation_sum", timeout=5)
    if res.status_code == 200:
        print("[OK] API Open-Meteo accessible.")
    else:
        print(f"[ERROR] Open-Meteo returned status {res.status_code}")
except Exception as e:
        print(f"[ERROR / TIMEOUT] Open-Meteo unreachable: {e}")

# 4. Check SoilGrids (ISRIC) with clean timeout handling and regional fallback
try:
    res = requests.get("https://rest.isric.org/soilgrids/v2.0/properties/query?lat=11.5564&lon=104.9282&property=phh2o&depth=0-5cm&value=mean", timeout=5)
    if res.status_code == 200:
        print("[OK] API SoilGrids accessible.")
    else:
        print(f"[AVERTISSEMENT] SoilGrids a répondu avec le code {res.status_code} (Le fallback régional s'activera)")
except Exception as e:
    print(f"[AVERTISSEMENT / TIMEOUT] SoilGrids injoignable : {e} (Le fallback régional s'activera)")

print("--- [HEALTHCHECK] Fin des vérifications ---")
