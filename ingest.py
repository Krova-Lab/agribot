import os
import sys
import re
import requests
import psycopg2
from dotenv import load_dotenv
from config.database import get_db_params

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("Error: API key not found in .env")
    sys.exit(1)

DB_PARAMS = get_db_params()

def chunk_text_multilingual(text, max_chars=1000):
    sentences = re.split(r'(?<=[.!?។])\s*', text)
    chunks = []
    current_chunk = ""
    for sentence in sentences:
        if not sentence.strip():
            continue
        if len(current_chunk) + len(sentence) > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            current_chunk += " " + sentence if current_chunk else sentence
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

def ingest_file(filepath):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    chunks = chunk_text_multilingual(content)
    title = os.path.basename(filepath)
    
    conn = psycopg2.connect(**DB_PARAMS)
    cursor = conn.cursor()
    
    print(f"Ingesting '{title}' ({len(chunks)} document chunks)...")
    
    # Use the same 3072-dimensional embeddings as the primary RAG table.
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={api_key}"
    
    for chunk in chunks:
        headers = {'Content-Type': 'application/json'}
        payload = {
            "model": "models/gemini-embedding-001",
            "content": {
                "parts": [{"text": chunk}]
            },
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code != 200:
            print(f"Google API error: HTTP {response.status_code}")
            continue
            
        data = response.json()
        embedding = data['embedding']['values']
        
        cursor.execute(
            "INSERT INTO rag_documents (source_title, category, content, embedding) VALUES (%s, %s, %s, %s)",
            (title, "ingested", chunk, embedding)
        )
            
    conn.commit()
    cursor.close()
    conn.close()
    print("Document successfully embedded and stored in pgvector.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        ingest_file(sys.argv[1])
    else:
        print("Usage: python ingest.py <chemin_vers_le_fichier.txt>")
