import os
import psycopg2
from google import genai
from config.database import get_db_params, PROJECT_ROOT
from source_policy import EXCLUDED_HISTORICAL_PREFIX, LEGACY_UNVERIFIED_TITLES
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)
DB_PARAMS = get_db_params()

def search_rag(query: str, limit: int = 2, *, raise_on_error: bool = False) -> str:
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
            WITH candidates AS (
                SELECT source_title, content, embedding
                FROM rag_documents
                WHERE embedding IS NOT NULL
                  AND audit_status = 'approved'
                  AND COALESCE(source_title, '') <> ALL(%s)
                  AND LEFT(COALESCE(source_title, ''), %s) <> %s
                UNION ALL
                SELECT kb.source_title, kb.content, kb.embedding
                FROM knowledge_base AS kb
                WHERE kb.embedding IS NOT NULL
                  AND COALESCE(kb.source_title, '') <> ALL(%s)
                  AND LEFT(COALESCE(kb.source_title, ''), %s) <> %s
                  AND NOT EXISTS (
                      SELECT 1 FROM rag_documents AS rd
                      WHERE rd.file_sha256 = kb.file_sha256
                  )
            )
            SELECT source_title, content, embedding <=> %s::vector AS distance
            FROM candidates
            ORDER BY distance ASC
            LIMIT %s;
        """, (
            list(LEGACY_UNVERIFIED_TITLES),
            len(EXCLUDED_HISTORICAL_PREFIX), EXCLUDED_HISTORICAL_PREFIX,
            list(LEGACY_UNVERIFIED_TITLES),
            len(EXCLUDED_HISTORICAL_PREFIX), EXCLUDED_HISTORICAL_PREFIX,
            query_vector, limit,
        ))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        return "\n\n".join([f"[{r[0]}] {r[1]}" for r in rows])
    except Exception as e:
        print(f"[RAG SEARCH ERROR] {e}")
        if raise_on_error:
            raise
        return ""

if __name__ == "__main__":
    test_q = "ឫសស្អុយចំបើងរលួយ"
    print("Vector search test for:", test_q)
    print(search_rag(test_q))
