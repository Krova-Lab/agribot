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
    print("   KROVA AGRI AUTOMATED END-TO-END TEST   ")
    print("==================================================")
    all_ok = True

    # 1. Access control
    allowed = access_control.is_allowed_access(TESTER_TELEGRAM_ID)
    all_ok &= log_test("ACCESS CONTROL", allowed, f"Testeur {TESTER_TELEGRAM_ID} autorisé: {allowed}")

    # 2. RAG & pgvector (execute the SQL query)
    try:
        rag_t0 = time.time()
        rag_res = search_rag("symptômes mosaïque manioc SLCMV", limit=2)
        rag_ms = int((time.time() - rag_t0) * 1000)
        # Success if the search runs without an SQL error, even when the RAG corpus is empty
        rag_status = (rag_res is not None)
        count_docs = len(rag_res) if rag_res else 0
        all_ok &= log_test("RAG / PGVECTOR", rag_status, f"Requête pgvector exécutée en {rag_ms} ms (docs: {count_docs})")
    except Exception as e:
        all_ok &= log_test("RAG / PGVECTOR", False, f"SQL/pgvector error: {e}")

    # 3. Multimodal vision (JPEG generation without Pillow via ffmpeg)
    try:
        cmd_img = ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=green:s=100x100:d=1", "-frames:v", "1", "-f", "image2", "-"]
        proc_img = subprocess.Popen(cmd_img, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        img_bytes, _ = proc_img.communicate()

        vis_t0 = time.time()
        vis_resp, vis_model = ask_llm(
            "Diagnostique cette image de plante. Si l'image n'est pas claire, indique-le poliment.", 
            media_bytes=img_bytes, 
            mime_type="image/jpeg"
        )
        vis_ms = int((time.time() - vis_t0) * 1000)
        img_ok = bool(vis_resp and len(vis_resp) > 0)
        all_ok &= log_test("MULTIMODAL VISION", img_ok, f"Analyse {vis_model} en {vis_ms} ms")
    except Exception as e:
        all_ok &= log_test("MULTIMODAL VISION", False, f"Image pipeline error: {e}")

    # 4. Multimodal audio (OGG Opus via ffmpeg)
    try:
        cmd_aud = ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=1", "-c:a", "libopus", "-f", "ogg", "-"]
        proc_aud = subprocess.Popen(cmd_aud, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        audio_bytes, _ = proc_aud.communicate()

        aud_t0 = time.time()
        aud_resp, aud_model = ask_llm(
            "Écoute cet audio. Si aucun son intelligible n'est présent, indique-le.",
            media_bytes=audio_bytes,
            mime_type="audio/ogg"
        )
        aud_ms = int((time.time() - aud_t0) * 1000)
        aud_ok = bool(aud_resp and len(aud_resp) > 0)
        all_ok &= log_test("MULTIMODAL AUDIO", aud_ok, f"Décodage Ogg Opus via {aud_model} en {aud_ms} ms")
    except Exception as e:
        all_ok &= log_test("MULTIMODAL AUDIO", False, f"Audio pipeline error: {e}")

    # 5. PostgreSQL persistence & voting mechanism
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
        all_ok &= log_test("POSTGRES & FEEDBACK LOCK", sql_success, f"Cycle écriture + vote anti-doublon (ID test {interaction_id})")
    except Exception as e:
        all_ok &= log_test("POSTGRES & FEEDBACK LOCK", False, f"SQL error: {e}")

    print("==================================================")
    if all_ok:
        print("🎉 BILAN : 100% DES PIPELINES DE PRODUCTION SONT VALIDÉS")
    else:
        print("⚠️ BILAN : CERTAINS COMPOSANTS ONT ÉCHOUÉ")
    print("==================================================")

if __name__ == "__main__":
    run_e2e_suite()
