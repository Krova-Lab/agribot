#!/usr/bin/env python3
import os
import re
import json
import hashlib
import psycopg2
from google import genai
from google.genai import types
from config.database import get_db_params
from config.prompt_loader import load_prompts, render_prompt

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

DB_PARAMS = get_db_params()
PROMPTS = load_prompts()

def compute_file_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def compute_content_sha256(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def check_duplicate(file_hash: str, content_hash: str = None) -> tuple[bool, str]:
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    # 1. Binary hash verification
    cur.execute("SELECT COALESCE(source_title, 'Document sans titre') FROM rag_documents WHERE file_sha256 = %s LIMIT 1", (file_hash,))
    res = cur.fetchone()
    if res:
        cur.close()
        conn.close()
        return True, f"Exact binary duplicate (already indexed as '{res[0]}')"

    # 2. Text hash verification
    if content_hash:
        cur.execute("SELECT COALESCE(source_title, 'Document sans titre') FROM rag_documents WHERE content_sha256 = %s LIMIT 1", (content_hash,))
        res = cur.fetchone()
        if res:
            cur.close()
            conn.close()
            return True, f"Text duplicate (same content as '{res[0]}')"

    cur.close()
    conn.close()
    return False, ""

def audit_document_content(text_sample: str, filename: str) -> dict:
    if not client:
        return {
            "trust_score": 0.0,
            "content_year": None,
            "detected_source": "Unknown (missing audit credentials)",
            "status": "pending",
            "reason": "Document audit was not run because audit credentials are unavailable."
        }

    prompt = render_prompt(
        PROMPTS["document_audit_prompt"],
        filename=filename,
        text_sample=text_sample[:2500],
    )

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = json.loads(response.text)
        return {
            "trust_score": float(data.get("trust_score", 0.7)),
            "content_year": data.get("content_year"),
            "detected_source": str(data.get("detected_source", "Unknown"))[:100],
            "status": "quarantine" if data.get("status") == "quarantine" else "pending",
            "reason": str(data.get("reason", "OK"))
        }
    except Exception as e:
        return {
            "trust_score": 0.0,
            "content_year": None,
            "detected_source": "Unknown (audit error)",
            "status": "pending",
            "reason": f"Document audit failed: {type(e).__name__}"
        }
