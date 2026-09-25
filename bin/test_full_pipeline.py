#!/usr/bin/env python3
"""
test_full_pipeline.py - Krova Agri end-to-end test (no extra dependencies)
"""
import os
import sys
import time
import subprocess
import psycopg2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import access_control
from config.database import get_db_params
from config.runtime import TESTER_TELEGRAM_ID
from rag_search import search_rag
from llm_adapter import ask_llm

DB_PARAMS = get_db_params()

def log_test(step, success, details=""):
    mark = "✅" if success else "❌"
    print(f"{mark} [{step}] {details}")
    return success

def run_e2e_suite():
    print("==================================================")
    print("   KROVA AGRI INTEGRATION SMOKE TEST   ")
    print("==================================================")
    all_ok = True

    # 1. Access control
    allowed = access_control.is_allowed_access(TESTER_TELEGRAM_ID)
    all_ok &= log_test("ACCESS CONTROL", allowed, f"Tester {TESTER_TELEGRAM_ID} allowed: {allowed}")

    # 2. Text generation route
    try:
        response_t0 = time.time()
        response, response_model = ask_llm(
            "Reply with exactly this token and nothing else: KROVA_AGRI_SMOKE_OK",
            task="response",
        )
        response_ms = int((time.time() - response_t0) * 1000)
        response_ok = bool(response and "KROVA_AGRI_SMOKE_OK" in response.upper())
        all_ok &= log_test("TEXT GENERATION", response_ok, f"Route {response_model} en {response_ms} ms")
    except Exception as e:
        all_ok &= log_test("TEXT GENERATION", False, f"Inference error: {e}")

    # 3. RAG & pgvector (execute the SQL query)
    try:
        rag_t0 = time.time()
        rag_res = search_rag("symptômes mosaïque manioc SLCMV", limit=2, raise_on_error=True)
        rag_ms = int((time.time() - rag_t0) * 1000)
        # An empty corpus is allowed in CI; database or embedding failures must still fail the check.
        count_docs = len(rag_res.split("\n\n")) if rag_res else 0
        all_ok &= log_test("RAG / PGVECTOR", True, f"Search completed in {rag_ms} ms (documents retrieved: {count_docs})")
    except Exception as e:
        all_ok &= log_test("RAG / PGVECTOR", False, f"SQL/pgvector error: {e}")

    # 4. Multimodal vision (synthetic JPEG connectivity check)
    try:
        cmd_img = ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=green:s=100x100:d=1", "-frames:v", "1", "-f", "image2", "-"]
        proc_img = subprocess.Popen(cmd_img, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        img_bytes, _ = proc_img.communicate()

        vis_t0 = time.time()
        vis_resp, vis_model = ask_llm(
            "Describe only what is visible. If this image is unclear, say so.",
            media_bytes=img_bytes, 
            mime_type="image/jpeg",
            task="vision",
        )
        vis_ms = int((time.time() - vis_t0) * 1000)
        img_ok = bool(vis_resp and len(vis_resp) > 0)
        all_ok &= log_test("MULTIMODAL VISION", img_ok, f"Analysis via {vis_model} in {vis_ms} ms")
    except Exception as e:
        all_ok &= log_test("MULTIMODAL VISION", False, f"Image pipeline error: {e}")

    # 5. Multimodal audio (synthetic OGG Opus connectivity check)
    try:
        cmd_aud = ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=1", "-c:a", "libopus", "-f", "ogg", "-"]
        proc_aud = subprocess.Popen(cmd_aud, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        audio_bytes, _ = proc_aud.communicate()

        aud_t0 = time.time()
        aud_resp, aud_model = ask_llm(
            "Transcribe intelligible speech only. If there is none, say 'No speech'.",
            media_bytes=audio_bytes,
            mime_type="audio/ogg",
            task="transcription",
        )
        aud_ms = int((time.time() - aud_t0) * 1000)
        aud_ok = bool(aud_resp and len(aud_resp) > 0)
        all_ok &= log_test("MULTIMODAL AUDIO", aud_ok, f"Ogg Opus decoding via {aud_model} in {aud_ms} ms")
    except Exception as e:
        all_ok &= log_test("MULTIMODAL AUDIO", False, f"Audio pipeline error: {e}")

    # 6. PostgreSQL persistence & voting mechanism
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO interactions 
            (telegram_id, role, has_text, raw_user_text, diagnosis_title, total_ms, model_used)
            VALUES (%s, 'tester', TRUE, 'Test unitaire automatisé', 'SLCMV Test', %s, 'gemini-3.6-flash')
            RETURNING id;
        """, (TESTER_TELEGRAM_ID, 1250))
        interaction_id = cur.fetchone()[0]
        conn.commit()

        # Initial vote
        cur.execute("UPDATE interactions SET rating_thumb = 1 WHERE id = %s AND rating_thumb IS NULL;", (interaction_id,))
        updated = (cur.rowcount == 1)
        conn.commit()

        # Concurrent replay (must fail)
        cur.execute("UPDATE interactions SET rating_thumb = -1 WHERE id = %s AND rating_thumb IS NULL;", (interaction_id,))
        double_vote_prevented = (cur.rowcount == 0)
        conn.commit()

        # Cleanup
        cur.execute("DELETE FROM interactions WHERE id = %s;", (interaction_id,))
        conn.commit()
        cur.close()
        conn.close()

        sql_success = updated and double_vote_prevented
        all_ok &= log_test("POSTGRES & FEEDBACK LOCK", sql_success, f"Write cycle + duplicate-vote protection (test ID {interaction_id})")
    except Exception as e:
        all_ok &= log_test("POSTGRES & FEEDBACK LOCK", False, f"SQL error: {e}")

    print("==================================================")
    if all_ok:
        print("✅ SUMMARY: all configured integration checks passed")
        print("This smoke test checks connectivity, not agronomic answer quality.")
    else:
        print("⚠️ SUMMARY: SOME COMPONENTS FAILED")
    print("==================================================")
    return bool(all_ok)

if __name__ == "__main__":
    raise SystemExit(0 if run_e2e_suite() else 1)
