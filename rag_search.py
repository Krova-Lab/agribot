import os
import psycopg2
from google import genai
from config.database import get_db_params, PROJECT_ROOT
from source_policy import LEGACY_UNVERIFIED_TITLES
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)
DB_PARAMS = get_db_params()

def search_rag(query: str, limit: int = 2) -> str:
    if not query or query == "[Photo sent]":
        return ""
    try:
        res = client.models.embed_content(
            model="models/gemini-embedding-001",
            contents=query
        )
        query_vector = res.embeddings[0].values
        
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        cur.execute("""
            SELECT source_title, content, (embedding <=> %s::vector) AS distance
            FROM rag_documents
            WHERE COALESCE(source_title, '') <> ALL(%s)
            ORDER BY distance ASC
            LIMIT %s;
        """, (query_vector, list(LEGACY_UNVERIFIED_TITLES), limit))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        return "\n\n".join([f"[{r[0]}] {r[1]}" for r in rows])
    except Exception as e:
        print(f"[RAG SEARCH ERROR] {e}")
        return ""

if __name__ == "__main__":
    test_q = "ឫសស្អុយចំបើងរលួយ"
    print("Vector search test for:", test_q)
    print(search_rag(test_q))
