import secrets
import time
import os
import json
from datetime import date
from typing import Optional, List, Literal
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor
from config.database import DB_HOST, DB_NAME, DB_PORT, DB_USER, DB_PASSWORD, PROJECT_ROOT

app = FastAPI(
    root_path="/agri-api",
    title="Krova Agri Backend API",
    version="1.1.0",
    description="Internal API for monitoring, agronomy moderation, and beta-tester management."
)

DB_PASS = DB_PASSWORD
DROPZONE_DIR = PROJECT_ROOT / "rag_dropzone"
API_TOKEN = os.getenv("KROVA_API_TOKEN")

def require_api_token(authorization: Optional[str] = Header(default=None)):
    """Protect the internal API with a fail-closed bearer token."""
    if not API_TOKEN:
        raise HTTPException(status_code=503, detail="Management API authentication is not configured")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(token, API_TOKEN):
        raise HTTPException(status_code=401, detail="Authentication required")

def get_db():
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS,
        port=DB_PORT, connect_timeout=3, cursor_factory=RealDictCursor
    )
    try:
        yield conn
    finally:
        conn.close()

# --- Pydantic models ---

class EnrollRequest(BaseModel):
    telegram_id: int
    username: Optional[str] = Field(default=None, max_length=128)
    role: Literal["tester", "user"] = "tester"
    preferred_language: Literal["km", "en", "fr"] = "km"

class UserResponse(BaseModel):
    telegram_id: int
    username: Optional[str]
    role: str
    is_active: bool
    preferred_language: str

class ReviewSubmission(BaseModel):
    interaction_id: int
    reviewer_telegram_id: Optional[int] = None
    reviewer_name: str = Field(max_length=100)
    status: str = Field(pattern="^(validated|corrected|flagged_rag|pending)$")
    corrected_diagnosis: Optional[str] = Field(default=None, max_length=20000)
    agronomist_notes: Optional[str] = Field(default=None, max_length=10000)

class PromoteRagRequest(BaseModel):
    interaction_id: int
    title: str = Field(max_length=256)
    crop: str = Field(default="General", max_length=128)
    source_url: str = Field(min_length=12, max_length=2048)
    source_publisher: Optional[str] = Field(default=None, max_length=256)
    source_publication_date: Optional[date] = None
    source_license: Optional[str] = Field(default=None, max_length=256)
    source_locator: Optional[str] = Field(default=None, max_length=256)

# --- Existing routes (health & users) ---

@app.get("/api/v1/health")
def health_check():
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS,
            port=DB_PORT, connect_timeout=3,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
        conn.close()
        return {"status": "healthy", "database": "reachable"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database readiness check failed") from exc

@app.get("/api/v1/users", response_model=List[UserResponse])
def list_users(_: None = Depends(require_api_token), conn=Depends(get_db)):
    with conn.cursor() as cur:
        cur.execute("SELECT telegram_id, username, role, is_active, preferred_language FROM bot_users ORDER BY created_at DESC;")
        return cur.fetchall()

@app.post("/api/v1/users/enroll")
def enroll_user(req: EnrollRequest, _: None = Depends(require_api_token), conn=Depends(get_db)):
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
def list_rag_documents(_: None = Depends(require_api_token), conn=Depends(get_db)):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, title, source, protocol_type, total_chunks, created_at
            FROM rag_documents
            ORDER BY created_at DESC LIMIT 50;
        """)
        return cur.fetchall()

@app.get("/api/v1/interactions")
def list_interactions(limit: int = 20, _: None = Depends(require_api_token), conn=Depends(get_db)):
    limit = max(1, min(limit, 100))
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
def list_pending_moderation(limit: int = 30, _: None = Depends(require_api_token), conn=Depends(get_db)):
    limit = max(1, min(limit, 100))
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
def submit_review(review: ReviewSubmission, _: None = Depends(require_api_token), conn=Depends(get_db)):
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
def get_analytics_overview(_: None = Depends(require_api_token), conn=Depends(get_db)):
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
            SELECT COALESCE(province, 'Not specified') AS province, COUNT(*) AS count
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
def promote_corrected_to_rag(req: PromoteRagRequest, _: None = Depends(require_api_token), conn=Depends(get_db)):
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
        raise HTTPException(status_code=404, detail="No corrected diagnosis was found for this interaction.")

    if not req.source_url.startswith(("https://", "http://")):
        raise HTTPException(status_code=422, detail="source_url must be an absolute HTTP(S) URL")

    # Create a Markdown record and a provenance sidecar in rag_dropzone.
    DROPZONE_DIR.mkdir(parents=True, exist_ok=True)
    file_name = f"krova_field_review_{secrets.token_hex(16)}.md"
    file_path = DROPZONE_DIR.resolve() / file_name

    doc_content = f"""# Field Review: {req.title}
Source: Krova Agri field moderation; not an official institutional protocol
Crop: {req.crop}
Reviewed by: {record.get('reviewer_name') or 'Not specified'}
Date: {time.strftime('%Y-%m-%d')}

## Observed Symptoms
{record.get('raw_user_text') or 'Description unavailable'}

## Reviewed Diagnosis & Recommended Treatment
{record['corrected_diagnosis']}

## Additional Notes & Precautions
{record.get('agronomist_notes') or 'None'}
"""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(doc_content)
        file_path.with_suffix(".source.json").write_text(
            json.dumps(
                {
                    "source_title": req.title,
                    "source_url": req.source_url,
                    "publisher": req.source_publisher,
                    "publication_date": req.source_publication_date.isoformat() if req.source_publication_date else None,
                    "license": req.source_license,
                    "page_or_section": req.source_locator,
                }, ensure_ascii=False, indent=2,
            ), encoding="utf-8",
        )
        return {"status": "promoted", "dropzone_file": file_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Dropzone write failed") from e
