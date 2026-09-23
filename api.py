from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
import os
from google import genai
from dotenv import load_dotenv
from config.database import get_db_params
from config.prompt_loader import load_prompts, render_prompt

# Load environment variables
load_dotenv(os.path.expanduser("~/agribot/.env"))
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

app = FastAPI(title="Krova Agri API")

class ChatRequest(BaseModel):
    question: str
    language: str = "fr"

DB_PARAMS = get_db_params()
PROMPTS = load_prompts()

@app.post("/api/chat")
def ask_agribot(request: ChatRequest):
    try:
        # 1. Embed the question
        emb_res = client.models.embed_content(
            model="models/gemini-embedding-001",
            contents=request.question,
        )
        query_vector = emb_res.embeddings[0].values

        # 2. Search PostgreSQL (top three)
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        sql = """
        SELECT source_title, content
        FROM rag_documents
        ORDER BY embedding <=> %s::vector
        LIMIT 3;
        """
        cursor.execute(sql, (query_vector,))
        results = cursor.fetchall()
        cursor.close()
        conn.close()

        if not results:
            return {"answer": "Je n'ai pas trouvé d'informations pertinentes dans ma base documentaire.", "sources": []}

        # 3. Assemble the context
        context_text = "\n\n---\n\n".join([f"Source [{row[0]}] : {row[1]}" for row in results])
        sources_list = list(set([row[0] for row in results]))
        
        prompt = render_prompt(
            PROMPTS["api_rag_prompt"],
            language=request.language,
            context_text=context_text,
            question=request.question,
        )

        # 4. Generate the response
        response = client.models.generate_content(
            model="gemini-3.6-flash", 
            contents=prompt,
        )

        return {
            "answer": response.text,
            "sources": sources_list
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
