import os
import time
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
from config.database import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, PROJECT_ROOT
from config.path_utils import safe_slug

app = FastAPI(
    root_path="/agri-api",
    title="Krova Agri Backend API",
    version="1.1.0",
    description="Internal API for monitoring, agronomy moderation, and beta-tester management."
)

DB_PASS = DB_PASSWORD
DROPZONE_DIR = PROJECT_ROOT / "rag_dropzone"

def get_db():
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS,
        cursor_factory=RealDictCursor
    )
    try:
        yield conn
    finally:
        conn.close()

# --- Pydantic models ---

class EnrollRequest(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    role: str = "tester"
    preferred_language: str = "km"

class UserResponse(BaseModel):
    telegram_id: int
    username: Optional[str]
    role: str
    is_active: bool
    preferred_language: str

class ReviewSubmission(BaseModel):
    interaction_id: int
    reviewer_telegram_id: Optional[int] = None
    reviewer_name: str
    status: str  # 'validated', 'corrected', 'flagged_rag'
    corrected_diagnosis: Optional[str] = None
    agronomist_notes: Optional[str] = None

class PromoteRagRequest(BaseModel):
    interaction_id: int
    title: str
    crop: str = "General"

# --- Existing routes (health & users) ---

@app.get("/api/v1/health")
def health_check(conn=Depends(get_db)):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS total_users FROM bot_users;")
        users = cur.fetchone()["total_users"]
        cur.execute("SELECT value FROM bot_settings WHERE key = 'access_mode';")
        mode = cur.fetchone()
    return {
        "status": "healthy",
        "database": "connected",
        "registered_users": users,
        "access_mode": mode["value"] if mode else "unknown"
    }

@app.get("/api/v1/users", response_model=List[UserResponse])
def list_users(conn=Depends(get_db)):
    with conn.cursor() as cur:
        cur.execute("SELECT telegram_id, username, role, is_active, preferred_language FROM bot_users ORDER BY created_at DESC;")
        return cur.fetchall()

@app.post("/api/v1/users/enroll")
def enroll_user(req: EnrollRequest, conn=Depends(get_db)):
    if req.role not in ["tester", "user", "admin", "ingestor"]:
        raise HTTPException(status_code=400, detail="Rôle invalide")
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO bot_users (telegram_id, username, role, is_active, preferred_language, updated_at)
            VALUES (%s, %s, %s, TRUE, %s, NOW())
            ON CONFLICT (telegram_id) DO UPDATE
            SET role = EXCLUDED.role, is_active = TRUE, preferred_language = EXCLUDED.preferred_language, updated_at = NOW();
        """, (req.telegram_id, req.username, req.role, req.preferred_language))
        conn.commit()
    return {"status": "enrolled", "telegram_id": req.telegram_id, "role": req.role}

@app.get("/api/v1/rag/documents")
def list_rag_documents(conn=Depends(get_db)):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, title, source, protocol_type, total_chunks, created_at
            FROM rag_documents
            ORDER BY created_at DESC LIMIT 50;
        """)
        return cur.fetchall()

@app.get("/api/v1/interactions")
def list_interactions(limit: int = 20, conn=Depends(get_db)):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                i.id,
                i.telegram_id,
                i.role,
                i.raw_user_text,
                i.diagnosis_title,
                i.confidence_score,
                i.model_used,
                i.province,
                i.rating_thumb,
                i.feedback_text,
                i.total_ms,
                i.created_at,
                r.status AS review_status,
                r.reviewer_name
            FROM interactions i
            LEFT JOIN diagnostic_reviews r ON i.id = r.interaction_id
            ORDER BY i.created_at DESC LIMIT %s;
        """, (limit,))
        return cur.fetchall()

# --- New endpoints: moderation & agronomic validation ---

@app.get("/api/v1/moderation/pending")
def list_pending_moderation(limit: int = 30, conn=Depends(get_db)):
    """Return interactions with negative feedback or no review first."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                i.id AS interaction_id,
                i.telegram_id,
                i.role,
                i.raw_user_text,
                i.diagnosis_title,
                i.confidence_score,
                i.province,
                i.soil_source,
                i.rating_thumb,
                i.feedback_category,
                i.feedback_text,
                i.created_at,
                r.status AS review_status,
                r.reviewer_name
            FROM interactions i
            LEFT JOIN diagnostic_reviews r ON i.id = r.interaction_id
            WHERE r.status IS NULL OR r.status = 'pending' OR i.rating_thumb = -1
            ORDER BY 
                CASE WHEN i.rating_thumb = -1 THEN 0 ELSE 1 END,
                i.created_at DESC
            LIMIT %s;
        """, (limit,))
        return cur.fetchall()

@app.post("/api/v1/moderation/review")
def submit_review(review: ReviewSubmission, conn=Depends(get_db)):
    """Create or update an expert agronomist review of a diagnosis."""
    if review.status not in ["validated", "corrected", "flagged_rag", "pending"]:
        raise HTTPException(status_code=400, detail="Statut de revue invalide.")

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO diagnostic_reviews (
                interaction_id, reviewer_telegram_id, reviewer_name,
                status, corrected_diagnosis, agronomist_notes, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (interaction_id) DO UPDATE SET
                reviewer_telegram_id = EXCLUDED.reviewer_telegram_id,
                reviewer_name = EXCLUDED.reviewer_name,
                status = EXCLUDED.status,
                corrected_diagnosis = EXCLUDED.corrected_diagnosis,
                agronomist_notes = EXCLUDED.agronomist_notes,
                updated_at = NOW()
            RETURNING id, status;
        """, (
            review.interaction_id, review.reviewer_telegram_id, review.reviewer_name,
            review.status, review.corrected_diagnosis, review.agronomist_notes
        ))
        row = cur.fetchone()
        conn.commit()

    return {"status": "success", "review_id": row["id"], "review_status": row["status"]}

@app.get("/api/v1/analytics/stats")
def get_analytics_overview(conn=Depends(get_db)):
    """Provide global metrics for the supervision dashboard."""
    with conn.cursor() as cur:
        # Total interactions & average latency
        cur.execute("""
            SELECT 
                COUNT(*) AS total_queries,
                COALESCE(AVG(total_ms), 0) AS avg_latency_ms,
                COUNT(CASE WHEN rating_thumb = 1 THEN 1 END) AS thumbs_up,
                COUNT(CASE WHEN rating_thumb = -1 THEN 1 END) AS thumbs_down
            FROM interactions;
        """)
        base_stats = cur.fetchone()

        # Breakdown by moderation status
        cur.execute("""
            SELECT status, COUNT(*) AS count 
            FROM diagnostic_reviews 
            GROUP BY status;
        """)
        review_stats = {r["status"]: r["count"] for r in cur.fetchall()}

        # Geographic breakdown (top five provinces)
        cur.execute("""
            SELECT COALESCE(province, 'Non spécifiée') AS province, COUNT(*) AS count
            FROM interactions
            GROUP BY province
            ORDER BY count DESC LIMIT 5;
        """)
        provinces = cur.fetchall()

    return {
        "summary": {
            "total_queries": base_stats["total_queries"],
            "avg_latency_ms": round(float(base_stats["avg_latency_ms"]), 2),
            "thumbs_up": base_stats["thumbs_up"],
            "thumbs_down": base_stats["thumbs_down"]
        },
        "moderation_reviews": review_stats,
        "provinces_breakdown": provinces
    }

@app.post("/api/v1/moderation/promote-to-rag")
def promote_corrected_to_rag(req: PromoteRagRequest, conn=Depends(get_db)):
    """Export a corrected agronomic recommendation to the RAG ingestion dropzone."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT i.raw_user_text, r.corrected_diagnosis, r.agronomist_notes, r.reviewer_name
            FROM diagnostic_reviews r
            JOIN interactions i ON r.interaction_id = i.id
            WHERE r.interaction_id = %s;
        """, (req.interaction_id,))
        record = cur.fetchone()

    if not record or not record.get("corrected_diagnosis"):
        raise HTTPException(status_code=404, detail="Aucun diagnostic corrigé trouvé pour cette interaction.")

    # Create a Markdown record in rag_dropzone
    clean_title = safe_slug(req.title.lower(), "diagnostic")
    clean_crop = safe_slug(req.crop.lower(), "general")
    ts = int(time.time())
    file_name = f"cardi_fiche_terrain_{clean_crop}_{clean_title}_{ts}.md"
    dropzone_root = DROPZONE_DIR.resolve()
    file_path = (dropzone_root / file_name).resolve()
    if dropzone_root not in file_path.parents:
        raise HTTPException(status_code=400, detail="Nom de fichier invalide.")

    doc_content = f"""# Protocole Agronomique Validé : {req.title}
Source: Field Agronomy Moderation (Krova Agri)
Culture : {req.crop}
Validé par : {record.get('reviewer_name', 'Agronome CARDI')}
Date : {time.strftime('%Y-%m-%d')}

## Observed Symptoms
{record.get('raw_user_text', 'Description non disponible')}

## Official Diagnosis & Recommended Treatment
{record['corrected_diagnosis']}

## Additional Notes & Precautions
{record.get('agronomist_notes', 'Aucune')}
"""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(doc_content)
        return {"status": "promoted", "dropzone_file": file_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dropzone write error: {str(e)}")
